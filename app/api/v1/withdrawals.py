from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    PageMeta,
    PaginatedResponse,
    RetryWithdrawalRequest,
    WithdrawalRead,
    WithdrawalRequest,
    WithdrawalStatusUpdate,
)
from app.services.withdrawal_service import WithdrawalService

router = APIRouter(tags=["withdrawals"])


@router.post(
    "/withdraw",
    response_model=WithdrawalRead,
    status_code=status.HTTP_201_CREATED,
    summary="Request a withdrawal from wallet",
)
def create_withdrawal(
    payload: WithdrawalRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> WithdrawalRead:
    w = WithdrawalService(db).request_withdrawal(
        payload.user_id,
        payload.amount,
        idempotency_key=payload.idempotency_key or idempotency_key,
    )
    return WithdrawalRead.model_validate(w)


@router.post(
    "/retry-withdrawal",
    response_model=WithdrawalRead,
    status_code=status.HTTP_201_CREATED,
    summary="Retry a failed/cancelled/rejected withdrawal",
)
def retry_withdrawal(
    payload: RetryWithdrawalRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
) -> WithdrawalRead:
    w = WithdrawalService(db).retry(
        payload.withdrawal_id,
        idempotency_key=payload.idempotency_key or idempotency_key,
    )
    return WithdrawalRead.model_validate(w)


@router.post(
    "/withdrawals/status",
    response_model=WithdrawalRead,
    summary="Update terminal status (provider callback / admin action)",
)
def update_status(payload: WithdrawalStatusUpdate, db: Session = Depends(get_db)) -> WithdrawalRead:
    w = WithdrawalService(db).update_status(
        payload.withdrawal_id, payload.status, reason=payload.reason
    )
    return WithdrawalRead.model_validate(w)


@router.get(
    "/withdrawals",
    response_model=PaginatedResponse[WithdrawalRead],
    summary="List a user's withdrawals",
)
def list_withdrawals(
    user_id: str = Query(..., min_length=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PaginatedResponse[WithdrawalRead]:
    offset = (page - 1) * page_size
    items, total = WithdrawalService(db).withdrawals.list_for_user(
        user_id, limit=page_size, offset=offset
    )
    return PaginatedResponse[WithdrawalRead](
        items=[WithdrawalRead.model_validate(w) for w in items],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )
