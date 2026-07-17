from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import SaleStatus
from app.schemas import PageMeta, PaginatedResponse, SaleCreate, SaleRead
from app.services.sale_service import SaleService

router = APIRouter(prefix="/sales", tags=["sales"])


@router.post(
    "",
    response_model=SaleRead,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a new sale",
)
def create_sale(payload: SaleCreate, db: Session = Depends(get_db)) -> SaleRead:
    sale = SaleService(db).create_sale(payload)
    return SaleRead.model_validate(sale)


@router.get(
    "",
    response_model=PaginatedResponse[SaleRead],
    summary="List / search sales",
)
def list_sales(
    user_id: str | None = Query(default=None, description="Filter by user"),
    status_: SaleStatus | None = Query(default=None, alias="status"),
    brand: str | None = Query(default=None),
    sort: str = Query(default="-created_at", pattern=r"^-?(created_at|earning|id)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
) -> PaginatedResponse[SaleRead]:
    offset = (page - 1) * page_size
    items, total = SaleService(db).search(
        user_id=user_id,
        status=status_,
        brand=brand,
        sort=sort,
        limit=page_size,
        offset=offset,
    )
    return PaginatedResponse[SaleRead](
        items=[SaleRead.model_validate(s) for s in items],
        meta=PageMeta(page=page, page_size=page_size, total=total),
    )
