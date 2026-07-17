from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Transaction
from app.models.enums import TransactionDirection, TransactionType


class TransactionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def record(
        self,
        *,
        user_id: str,
        type_: TransactionType,
        direction: TransactionDirection,
        amount: Decimal,
        balance_after: Decimal,
        reference_type: str | None = None,
        reference_id: str | int | None = None,
        description: str | None = None,
    ) -> Transaction:
        txn = Transaction(
            user_id=user_id,
            type=type_.value,
            direction=direction.value,
            amount=amount,
            balance_after=balance_after,
            reference_type=reference_type,
            reference_id=str(reference_id) if reference_id is not None else None,
            description=description,
        )
        self.db.add(txn)
        self.db.flush()
        return txn

    def list_for_user(
        self,
        user_id: str,
        *,
        type_: TransactionType | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Transaction], int]:
        base = select(Transaction).where(Transaction.user_id == user_id)
        if type_:
            base = base.where(Transaction.type == type_.value)
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        stmt = base.order_by(Transaction.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt)), int(total)
