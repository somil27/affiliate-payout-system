"""AdvancePayout — records the 10% advance transferred per sale.

The UNIQUE constraint on sale_id enforces "one advance per sale" at the DB
layer, which is what makes the advance-payout endpoint truly idempotent
even under concurrent duplicate requests.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base

if TYPE_CHECKING:
    from app.models.sale import Sale


class AdvancePayout(Base):
    __tablename__ = "advance_payouts"
    __table_args__ = (
        UniqueConstraint("sale_id", name="uq_advance_payout_sale"),
        CheckConstraint("amount >= 0", name="ck_advance_amount_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sale_id: Mapped[int] = mapped_column(
        ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sale: Mapped["Sale"] = relationship(back_populates="advance_payout")
