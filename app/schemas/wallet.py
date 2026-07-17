from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class WalletRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: str
    available_balance: Decimal
    lifetime_earned: Decimal
    updated_at: datetime
