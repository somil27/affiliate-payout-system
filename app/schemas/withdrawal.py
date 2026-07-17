from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import WithdrawalStatus


class WithdrawalRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    amount: Decimal = Field(gt=Decimal("0"))
    idempotency_key: str | None = Field(default=None, max_length=80)


class WithdrawalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    amount: Decimal
    status: WithdrawalStatus
    idempotency_key: str | None
    retried_from_id: int | None
    failure_reason: str | None
    created_at: datetime
    settled_at: datetime | None


class RetryWithdrawalRequest(BaseModel):
    """Reopen a failed/cancelled/rejected withdrawal for another attempt."""

    withdrawal_id: int
    idempotency_key: str | None = Field(default=None, max_length=80)


class WithdrawalStatusUpdate(BaseModel):
    """Admin / provider callback to mark a pending withdrawal terminal."""

    withdrawal_id: int
    status: WithdrawalStatus
    reason: str | None = Field(default=None, max_length=255)
