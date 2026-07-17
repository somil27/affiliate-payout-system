"""Sale model — one row per affiliate sale."""
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
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.models.enums import SaleStatus

if TYPE_CHECKING:
    from app.models.advance_payout import AdvancePayout
    from app.models.user import User


class Sale(Base):
    __tablename__ = "sales"
    __table_args__ = (
        # A caller-supplied external_id makes sale ingestion idempotent per user.
        UniqueConstraint("user_id", "external_id", name="uq_sales_user_external"),
        CheckConstraint("earning >= 0", name="ck_sales_earning_non_negative"),
        Index("ix_sales_user_status", "user_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    brand: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    earning: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=SaleStatus.PENDING.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reconciled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="sales")
    advance_payout: Mapped["AdvancePayout | None"] = relationship(
        back_populates="sale", uselist=False, cascade="all, delete-orphan"
    )
