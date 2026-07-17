"""Withdrawal + audit log."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.enums import WithdrawalStatus

if TYPE_CHECKING:
    from app.models.user import User


class Withdrawal(Base):
    __tablename__ = "withdrawals"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_withdrawal_amount_positive"),
        Index("ix_withdrawals_user_created", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=WithdrawalStatus.PENDING.value
    )
    idempotency_key: Mapped[str | None] = mapped_column(
        String(80), nullable=True, unique=True, index=True
    )
    # Set when the withdrawal is reopened via /retry-withdrawal.
    retried_from_id: Mapped[int | None] = mapped_column(
        ForeignKey("withdrawals.id", ondelete="SET NULL"), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="withdrawals")
    history: Mapped[list["WithdrawalHistory"]] = relationship(
        back_populates="withdrawal",
        cascade="all, delete-orphan",
        order_by="WithdrawalHistory.created_at",
    )


class WithdrawalHistory(Base):
    """Append-only status transition log for a withdrawal."""

    __tablename__ = "withdrawal_history"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    withdrawal_id: Mapped[int] = mapped_column(
        ForeignKey("withdrawals.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    withdrawal: Mapped["Withdrawal"] = relationship(back_populates="history")
