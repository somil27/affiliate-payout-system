from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import TransactionType
from app.schemas import PageMeta, PaginatedResponse, TransactionRead
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get(
    "",
    response_model=PaginatedResponse[TransactionRead],
    summary="List a user's wallet transactions",
)
def list_transactions(
    user_id: str = Query(..., min_length=1),
    type_: TransactionType | None = Query(default=None, alias="type"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PaginatedResponse[TransactionRead]:
    offset = (page - 1) * page_size
    items, total = WalletService(db).list_transactions(
        user_id, type_=type_, limit=page_size, offset=offset
    )
    return PaginatedResponse[TransactionRead](
        items=[TransactionRead.model_validate(t) for t in items],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )
