from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import (
    InvalidStateError,
    NotFoundError,
    RateLimitedError,
)
from app.models import Withdrawal
from app.models.enums import TransactionDirection, TransactionType, WithdrawalStatus
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.wallet_repository import WalletRepository
from app.repositories.withdrawal_repository import WithdrawalRepository

logger = logging.getLogger(__name__)


class WithdrawalService:
    """Create withdrawals, update their status, and reverse funds on failure.

    Business rules encoded here:
      * Max ONE non-failed withdrawal per user per cooldown window.
      * Withdrawal amount must be <= wallet.available_balance.
      * Idempotency-key replays return the original withdrawal record.
      * On terminal failure (cancelled / rejected / failed) the debited
        amount is credited back to the wallet in the same transaction.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.users = UserRepository(db)
        self.wallets = WalletRepository(db)
        self.withdrawals = WithdrawalRepository(db)
        self.transactions = TransactionRepository(db)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    def request_withdrawal(
        self, user_id: str, amount: Decimal, *, idempotency_key: str | None = None
    ) -> Withdrawal:
        if amount <= 0:
            raise InvalidStateError("Withdrawal amount must be positive")

        if idempotency_key:
            existing = self.withdrawals.get_by_idempotency(idempotency_key)
            if existing is not None:
                return existing

        if self.users.get(user_id) is None:
            raise NotFoundError(f"User '{user_id}' does not exist")

        self._enforce_cooldown(user_id)

        wallet = self.wallets.get_locked(user_id)
        amount = amount.quantize(Decimal("0.01"))
        new_balance = self.wallets.debit(wallet, amount)

        withdrawal = Withdrawal(
            user_id=user_id,
            amount=amount,
            status=WithdrawalStatus.PENDING.value,
            idempotency_key=idempotency_key,
        )
        self.withdrawals.add(withdrawal)
        self.withdrawals.add_history(
            withdrawal, from_status=None, to_status=WithdrawalStatus.PENDING.value,
            note="Withdrawal requested",
        )
        self.transactions.record(
            user_id=user_id,
            type_=TransactionType.WITHDRAWAL,
            direction=TransactionDirection.DEBIT,
            amount=amount,
            balance_after=new_balance,
            reference_type="withdrawal",
            reference_id=withdrawal.id,
            description="Withdrawal requested",
        )
        self.db.commit()
        self.db.refresh(withdrawal)
        logger.info(
            "withdrawal.created",
            extra={"user_id": user_id, "withdrawal_id": withdrawal.id, "amount": str(amount)},
        )
        return withdrawal

    # ------------------------------------------------------------------
    # Status transition (provider callback / admin)
    # ------------------------------------------------------------------
    def update_status(
        self, withdrawal_id: int, new_status: WithdrawalStatus, *, reason: str | None = None
    ) -> Withdrawal:
        withdrawal = self.withdrawals.get(withdrawal_id)
        if withdrawal is None:
            raise NotFoundError(f"Withdrawal {withdrawal_id} not found")

        current = WithdrawalStatus(withdrawal.status)
        if current == new_status:
            return withdrawal  # idempotent no-op
        if current != WithdrawalStatus.PENDING:
            raise InvalidStateError(
                f"Cannot transition withdrawal from '{current.value}' to '{new_status.value}'"
            )

        wallet = self.wallets.get_locked(withdrawal.user_id)

        withdrawal.status = new_status.value
        withdrawal.settled_at = datetime.now(timezone.utc)
        withdrawal.failure_reason = reason if new_status in WithdrawalStatus.failure_states() else None

        self.withdrawals.add_history(
            withdrawal,
            from_status=current.value,
            to_status=new_status.value,
            note=reason,
        )

        if new_status in WithdrawalStatus.failure_states():
            new_balance = self.wallets.credit(wallet, withdrawal.amount)
            self.transactions.record(
                user_id=withdrawal.user_id,
                type_=TransactionType.WITHDRAWAL_REVERSAL,
                direction=TransactionDirection.CREDIT,
                amount=withdrawal.amount,
                balance_after=new_balance,
                reference_type="withdrawal",
                reference_id=withdrawal.id,
                description=f"Reversal of {new_status.value} withdrawal: {reason or ''}".strip(),
            )
            logger.info(
                "withdrawal.reversed",
                extra={
                    "withdrawal_id": withdrawal.id,
                    "user_id": withdrawal.user_id,
                    "amount": str(withdrawal.amount),
                    "reason": reason,
                },
            )

        self.db.commit()
        self.db.refresh(withdrawal)
        return withdrawal

    # ------------------------------------------------------------------
    # Retry
    # ------------------------------------------------------------------
    def retry(self, withdrawal_id: int, *, idempotency_key: str | None = None) -> Withdrawal:
        original = self.withdrawals.get(withdrawal_id)
        if original is None:
            raise NotFoundError(f"Withdrawal {withdrawal_id} not found")
        if WithdrawalStatus(original.status) not in WithdrawalStatus.failure_states():
            raise InvalidStateError(
                "Only failed / cancelled / rejected withdrawals can be retried"
            )

        # Retries bypass the cooldown because the original attempt already
        # consumed it; the reversal put the funds back so a re-attempt is
        # a natural continuation, not a "new" withdrawal.
        if idempotency_key:
            existing = self.withdrawals.get_by_idempotency(idempotency_key)
            if existing is not None:
                return existing

        wallet = self.wallets.get_locked(original.user_id)
        new_balance = self.wallets.debit(wallet, original.amount)

        retry = Withdrawal(
            user_id=original.user_id,
            amount=original.amount,
            status=WithdrawalStatus.PENDING.value,
            idempotency_key=idempotency_key,
            retried_from_id=original.id,
        )
        self.withdrawals.add(retry)
        self.withdrawals.add_history(
            retry,
            from_status=None,
            to_status=WithdrawalStatus.PENDING.value,
            note=f"Retry of withdrawal {original.id}",
        )
        self.transactions.record(
            user_id=original.user_id,
            type_=TransactionType.WITHDRAWAL,
            direction=TransactionDirection.DEBIT,
            amount=original.amount,
            balance_after=new_balance,
            reference_type="withdrawal",
            reference_id=retry.id,
            description=f"Retry of withdrawal {original.id}",
        )
        self.db.commit()
        self.db.refresh(retry)
        logger.info(
            "withdrawal.retried",
            extra={
                "user_id": original.user_id,
                "original_id": original.id,
                "new_withdrawal_id": retry.id,
            },
        )
        return retry

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _enforce_cooldown(self, user_id: str) -> None:
        window_start = datetime.now(timezone.utc) - timedelta(
            hours=self.settings.withdrawal_cooldown_hours
        )
        recent = self.withdrawals.latest_non_failed_within(user_id, since=window_start)
        if recent is not None:
            raise RateLimitedError(
                f"Only one withdrawal per {self.settings.withdrawal_cooldown_hours}h. "
                f"Last request at {recent.created_at.isoformat()}."
            )
