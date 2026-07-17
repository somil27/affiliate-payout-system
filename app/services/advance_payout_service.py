from __future__ import annotations

import logging
import threading
from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError
from app.models import AdvancePayout
from app.models.enums import TransactionDirection, TransactionType
from app.repositories.advance_payout_repository import AdvancePayoutRepository
from app.repositories.sale_repository import SaleRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.user_repository import UserRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.payout import AdvancePayoutResponse, AdvancePayoutSaleResult

logger = logging.getLogger(__name__)

# Bounded retries for the wallet's optimistic-lock (version_id_col) conflict.
#
# `wallets.get_locked()` takes a pessimistic SELECT ... FOR UPDATE, but that
# only serializes concurrent transactions on backends/isolation levels where
# the lock is actually enforced for the whole transaction lifetime. Across
# separate DB connections/processes (e.g. multiple app workers against real
# Postgres) two requests for the same user can still both reach the point of
# mutating the in-memory `wallet` object before either commits, so the
# loser's UPDATE ... WHERE id = ? AND version = ? matches zero rows and
# SQLAlchemy raises StaleDataError instead of silently corrupting data.
#
# Rather than surface that as a 500, we roll back and re-run the operation.
# The retry re-reads the wallet (now at the winner's committed version) and
# re-lists pending sales (now excluding whatever the winner already
# advanced, thanks to the UNIQUE(sale_id) constraint on advance_payouts), so
# it naturally converges to the correct, idempotent result — sales already
# paid by the other request come back as `already_paid`, and only genuinely
# unpaid sales get credited.
_MAX_VERSION_CONFLICT_RETRIES = 5

# In-process, per-user serialization for the advance-payout critical section.
#
# Within a single process (e.g. one uvicorn/gunicorn worker — the same unit
# that owns one DB connection/pool slot), FastAPI can genuinely run two
# requests for the same user's wallet on separate threads at the same time.
# `wallets.get_locked()`'s SELECT ... FOR UPDATE only protects the DB row;
# it does nothing to stop two threads from concurrently driving the *same*
# underlying DBAPI connection (as happens with SQLite/StaticPool, and can
# also happen with a checked-out connection shared across threads), which
# surfaces as low-level errors such as sqlalchemy.orm.exc.FlushError or
# sqlite3.InterfaceError rather than a clean StaleDataError.
#
# A small per-user-id lock closes that gap cheaply, without touching the
# DB layer, schema, or locking strategy: only one request per user_id runs
# the payout body at a time *in this process*; different users still run
# fully in parallel. This is additive defense-in-depth alongside (not a
# replacement for) the DB-level version_id_col + SELECT FOR UPDATE, which
# remain the source of truth for correctness across multiple processes.
_user_locks: dict[str, threading.Lock] = {}
_user_locks_guard = threading.Lock()


def _lock_for_user(user_id: str) -> threading.Lock:
    with _user_locks_guard:
        lock = _user_locks.get(user_id)
        if lock is None:
            lock = threading.Lock()
            _user_locks[user_id] = lock
        return lock


class AdvancePayoutService:
    """Pay out 10% of pending-sale earnings to the user's wallet.

    Idempotency is enforced at TWO layers:
      1. Application: we skip any sale that already has an advance_payout row.
      2. Database  : UNIQUE(sale_id) on advance_payouts, so a concurrent
         duplicate request fails with IntegrityError which we swallow.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.users = UserRepository(db)
        self.sales = SaleRepository(db)
        self.wallets = WalletRepository(db)
        self.advances = AdvancePayoutRepository(db)
        self.transactions = TransactionRepository(db)

    def pay_advance(
        self, user_id: str, *, idempotency_key: str | None = None
    ) -> AdvancePayoutResponse:
        """Public entry point.

        Serializes concurrent requests for the same user (in-process lock)
        and retries the operation on wallet version conflicts (cross-process
        races on the DB). Never lets StaleDataError/FlushError/driver-level
        errors escape as a 500 — either a retry succeeds (the common case)
        and returns a normal, idempotent response, or retries are exhausted
        (practically never happens) and we raise a 409 Conflict instead.
        """
        with _lock_for_user(user_id):
            last_error: Exception | None = None
            for attempt in range(1, _MAX_VERSION_CONFLICT_RETRIES + 1):
                try:
                    return self._pay_advance_once(user_id, idempotency_key=idempotency_key)
                except StaleDataError as exc:
                    last_error = exc
                    # The failed flush leaves the session unusable until
                    # rolled back; roll back so the next attempt starts clean.
                    self.db.rollback()
                    logger.info(
                        "advance_payout.version_conflict_retry",
                        extra={"user_id": user_id, "attempt": attempt},
                    )

            logger.warning(
                "advance_payout.version_conflict_exhausted",
                extra={"user_id": user_id, "attempts": _MAX_VERSION_CONFLICT_RETRIES},
            )
            raise ConflictError(
                "Advance payout is being processed by another concurrent request; "
                "please retry.",
            ) from last_error

    def _pay_advance_once(
        self, user_id: str, *, idempotency_key: str | None = None
    ) -> AdvancePayoutResponse:
        user = self.users.get(user_id)
        if user is None:
            raise NotFoundError(f"User '{user_id}' does not exist")

        wallet = self.wallets.get_locked(user_id)
        pending_sales = self.sales.list_pending_without_advance(user_id)

        results: list[AdvancePayoutSaleResult] = []
        total_credited = Decimal("0.00")
        rate = self.settings.advance_payout_rate

        for sale in pending_sales:
            amount = (sale.earning * rate).quantize(Decimal("0.01"))
            if amount <= 0:
                continue

            advance = AdvancePayout(
                sale_id=sale.id,
                user_id=user_id,
                amount=amount,
                idempotency_key=idempotency_key,
            )
            try:
                # SAVEPOINT so a concurrent duplicate for this sale doesn't
                # abort the whole batch.
                with self.db.begin_nested():
                    self.advances.add(advance)
            except IntegrityError:
                logger.info(
                    "advance_payout.duplicate_skipped",
                    extra={"sale_id": sale.id, "user_id": user_id},
                )
                results.append(
                    AdvancePayoutSaleResult(sale_id=sale.id, amount=Decimal("0.00"), already_paid=True)
                )
                continue

            new_balance = self.wallets.credit(wallet, amount)
            self.transactions.record(
                user_id=user_id,
                type_=TransactionType.ADVANCE_PAYOUT,
                direction=TransactionDirection.CREDIT,
                amount=amount,
                balance_after=new_balance,
                reference_type="sale",
                reference_id=sale.id,
                description=f"Advance payout ({int(rate * 100)}%) for sale {sale.id}",
            )
            total_credited += amount
            results.append(AdvancePayoutSaleResult(sale_id=sale.id, amount=amount))

        self.db.commit()
        self.db.refresh(wallet)
        logger.info(
            "advance_payout.completed",
            extra={
                "user_id": user_id,
                "total_credited": str(total_credited),
                "sales_processed": len(results),
            },
        )
        return AdvancePayoutResponse(
            user_id=user_id,
            total_advance_credited=total_credited,
            sales=results,
            wallet_balance=wallet.available_balance,
        )