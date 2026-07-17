"""Immutable double-entry-lite transaction log.

Every wallet mutation MUST write a transaction row so that the wallet
balance can be reconstructed from the log. This is the audit backbone.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.session import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        Index("ix_txn_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # credit | debit
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)

    # Weak references — the target object may live in a different table.
    reference_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reference_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
