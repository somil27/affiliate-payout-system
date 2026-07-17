"""User model."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base

if TYPE_CHECKING:
    from app.models.sale import Sale
    from app.models.wallet import Wallet
    from app.models.withdrawal import Withdrawal


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    sales: Mapped[list["Sale"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    wallet: Mapped["Wallet"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    withdrawals: Mapped[list["Withdrawal"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
