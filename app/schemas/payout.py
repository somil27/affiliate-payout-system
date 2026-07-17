from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field


class AdvancePayoutRequest(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    idempotency_key: str | None = Field(
        default=None,
        max_length=80,
        description="Optional client-provided key to make retries safe.",
    )


class AdvancePayoutSaleResult(BaseModel):
    sale_id: int
    amount: Decimal
    already_paid: bool = False


class AdvancePayoutResponse(BaseModel):
    user_id: str
    total_advance_credited: Decimal
    sales: list[AdvancePayoutSaleResult]
    wallet_balance: Decimal
