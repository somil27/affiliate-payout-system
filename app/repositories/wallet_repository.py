from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import InsufficientFundsError, NotFoundError
from app.models import Wallet


class WalletRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_for_user(self, user_id: str) -> Wallet | None:
        stmt = select(Wallet).where(Wallet.user_id == user_id)
        return self.db.scalars(stmt).first()

    def get_locked(self, user_id: str) -> Wallet:
        """Fetch the wallet with row-level lock; raise if missing."""
        stmt = select(Wallet).where(Wallet.user_id == user_id).with_for_update()
        wallet = self.db.scalars(stmt).first()
        if wallet is None:
            raise NotFoundError(f"Wallet not found for user '{user_id}'")
        return wallet

    def credit(self, wallet: Wallet, amount: Decimal) -> Decimal:
        if amount < 0:
            raise ValueError("credit amount must be non-negative")
        wallet.available_balance = (wallet.available_balance + amount).quantize(Decimal("0.01"))
        return wallet.available_balance

    def debit(self, wallet: Wallet, amount: Decimal, *, allow_negative: bool = False) -> Decimal:
        if amount < 0:
            raise ValueError("debit amount must be non-negative")
        new_balance = wallet.available_balance - amount
        if new_balance < 0 and not allow_negative:
            raise InsufficientFundsError(
                f"Insufficient balance: have {wallet.available_balance}, need {amount}"
            )
        wallet.available_balance = new_balance.quantize(Decimal("0.01"))
        return wallet.available_balance

    def add_lifetime(self, wallet: Wallet, amount: Decimal) -> None:
        wallet.lifetime_earned = (wallet.lifetime_earned + amount).quantize(Decimal("0.01"))
