from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AdvancePayout


class AdvancePayoutRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_sale(self, sale_id: int) -> AdvancePayout | None:
        stmt = select(AdvancePayout).where(AdvancePayout.sale_id == sale_id)
        return self.db.scalars(stmt).first()

    def add(self, advance: AdvancePayout) -> AdvancePayout:
        self.db.add(advance)
        self.db.flush()
        return advance

    def delete(self, advance: AdvancePayout) -> None:
        self.db.delete(advance)
        self.db.flush()
