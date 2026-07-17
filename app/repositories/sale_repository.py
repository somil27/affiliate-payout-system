from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Sale
from app.models.enums import SaleStatus


class SaleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, sale_id: int) -> Sale | None:
        return self.db.get(Sale, sale_id)

    def get_locked(self, sale_id: int) -> Sale | None:
        """Row-level lock for reconciliation (SELECT ... FOR UPDATE where supported)."""
        stmt = select(Sale).where(Sale.id == sale_id).with_for_update()
        return self.db.scalars(stmt).first()

    def find_by_external(self, user_id: str, external_id: str) -> Sale | None:
        stmt = select(Sale).where(
            Sale.user_id == user_id, Sale.external_id == external_id
        )
        return self.db.scalars(stmt).first()

    def add(self, sale: Sale) -> Sale:
        self.db.add(sale)
        self.db.flush()
        return sale

    def list_pending_without_advance(self, user_id: str) -> list[Sale]:
        """Pending sales that don't yet have an advance payout row."""
        stmt = (
            select(Sale)
            .options(joinedload(Sale.advance_payout))
            .where(Sale.user_id == user_id, Sale.status == SaleStatus.PENDING.value)
            .order_by(Sale.created_at.asc())
        )
        rows = self.db.scalars(stmt).unique().all()
        return [s for s in rows if s.advance_payout is None]

    def search(
        self,
        *,
        user_id: str | None = None,
        status: SaleStatus | None = None,
        brand: str | None = None,
        sort: str = "-created_at",
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Sale], int]:
        base = select(Sale)
        if user_id:
            base = base.where(Sale.user_id == user_id)
        if status:
            base = base.where(Sale.status == status.value)
        if brand:
            base = base.where(Sale.brand == brand)

        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0

        sort_col = {
            "created_at": Sale.created_at,
            "earning": Sale.earning,
            "id": Sale.id,
        }.get(sort.lstrip("-"), Sale.created_at)
        order = sort_col.desc() if sort.startswith("-") else sort_col.asc()

        stmt = base.order_by(order).limit(limit).offset(offset)
        return list(self.db.scalars(stmt)), int(total)
