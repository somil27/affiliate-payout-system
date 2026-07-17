from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models import Wallet
from app.models.enums import TransactionType
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.wallet_repository import WalletRepository


class WalletService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.wallets = WalletRepository(db)
        self.transactions = TransactionRepository(db)

    def get_wallet(self, user_id: str) -> Wallet:
        wallet = self.wallets.get_for_user(user_id)
        if wallet is None:
            raise NotFoundError(f"Wallet for user '{user_id}' not found")
        return wallet

    def list_transactions(
        self,
        user_id: str,
        *,
        type_: TransactionType | None = None,
        limit: int = 50,
        offset: int = 0,
    ):
        return self.transactions.list_for_user(
            user_id, type_=type_, limit=limit, offset=offset
        )
