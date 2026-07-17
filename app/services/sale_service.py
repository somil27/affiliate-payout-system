from __future__ import annotations

from decimal import Decimal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError
from app.models import Sale
from app.models.enums import SaleStatus
from app.repositories.sale_repository import SaleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.sale import SaleCreate


class SaleService:
    """Ingest sales.

    * Auto-creates the user + wallet on first sale.
    * Deduplicates by (user_id, external_id) when the client supplies one.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.sales = SaleRepository(db)

    def create_sale(self, payload: SaleCreate) -> Sale:
        self.users.get_or_create(payload.user_id)

        if payload.external_id:
            existing = self.sales.find_by_external(payload.user_id, payload.external_id)
            if existing is not None:
                # Idempotent create – return the previously stored sale.
                return existing

        sale = Sale(
            user_id=payload.user_id,
            brand=payload.brand,
            earning=payload.earning,
            external_id=payload.external_id,
            status=SaleStatus.PENDING.value,
        )
        try:
            self.sales.add(sale)
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            # Race: another concurrent request inserted the same external_id.
            if payload.external_id:
                existing = self.sales.find_by_external(payload.user_id, payload.external_id)
                if existing is not None:
                    return existing
            raise ConflictError("Duplicate sale") from exc
        self.db.refresh(sale)
        return sale

    def search(self, **kwargs) -> tuple[list[Sale], int]:
        return self.sales.search(**kwargs)
