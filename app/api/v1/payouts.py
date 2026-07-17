from __future__ import annotations

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AdvancePayoutRequest, AdvancePayoutResponse
from app.services.advance_payout_service import AdvancePayoutService

router = APIRouter(tags=["payouts"])


@router.post(
    "/advance-payout",
    response_model=AdvancePayoutResponse,
    status_code=status.HTTP_200_OK,
    summary="Credit 10% advance for all eligible pending sales",
)
def advance_payout(
    payload: AdvancePayoutRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> AdvancePayoutResponse:
    return AdvancePayoutService(db).pay_advance(
        payload.user_id,
        idempotency_key=payload.idempotency_key or idempotency_key,
    )
