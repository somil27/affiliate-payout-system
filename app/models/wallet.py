"""Wallet — a per-user single-row aggregate of money movement.

Split into two balances:
  * available_balance – money the user may withdraw right now.
  * lifetime_earned   – informational running total (approved payouts).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base

if TYPE_CHECKING:
    from app.models.user import User


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        CheckConstraint("available_balance >= 0", name="ck_wallet_available_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    available_balance: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    lifetime_earned: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0")
    )
    # Optimistic concurrency guard for wallet mutations.
    version: Mapped[int] = mapped_column(nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="wallet")

    __mapper_args__ = {"version_id_col": version}
