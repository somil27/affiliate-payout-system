from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import SaleStatus


class SaleCreate(BaseModel):
    user_id: str = Field(min_length=1, max_length=64)
    brand: str = Field(min_length=1, max_length=64)
    earning: Decimal = Field(gt=Decimal("0"), description="Earning in currency units")
    external_id: str | None = Field(default=None, max_length=64)

    @field_validator("earning")
    @classmethod
    def _quantize(cls, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"))


class SaleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    external_id: str | None
    user_id: str
    brand: str
    earning: Decimal
    status: SaleStatus
    created_at: datetime
    reconciled_at: datetime | None


class ReconcileItem(BaseModel):
    sale_id: int
    status: SaleStatus

    @field_validator("status")
    @classmethod
    def _not_pending(cls, v: SaleStatus) -> SaleStatus:
        if v == SaleStatus.PENDING:
            raise ValueError("Reconciliation status must be 'approved' or 'rejected'")
        return v


class ReconcileRequest(BaseModel):
    items: list[ReconcileItem] = Field(min_length=1)


class ReconcileResponse(BaseModel):
    user_id: str
    approved_count: int
    rejected_count: int
    credited_amount: Decimal  # sum of approved remainders
    reversed_amount: Decimal  # sum of rejected advance reversals
    net_adjustment: Decimal   # credited - reversed
    wallet_balance: Decimal
