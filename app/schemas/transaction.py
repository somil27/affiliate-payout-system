from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.enums import TransactionDirection, TransactionType


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: str
    type: TransactionType
    direction: TransactionDirection
    amount: Decimal
    balance_after: Decimal
    reference_type: str | None
    reference_id: str | None
    description: str | None
    created_at: datetime
