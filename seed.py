"""Idempotent seed data for local development.

Usage:
    python seed.py
"""
from __future__ import annotations

from decimal import Decimal

from app.database import SessionLocal, init_db
from app.repositories.sale_repository import SaleRepository
from app.repositories.user_repository import UserRepository
from app.schemas.sale import SaleCreate
from app.services.sale_service import SaleService


SEED_USERS = ["john_doe", "jane_smith"]

SEED_SALES = [
    ("john_doe", "brand_1", Decimal("40.00"), "seed-john-1"),
    ("john_doe", "brand_1", Decimal("40.00"), "seed-john-2"),
    ("john_doe", "brand_1", Decimal("40.00"), "seed-john-3"),
    ("jane_smith", "brand_2", Decimal("150.00"), "seed-jane-1"),
]


def main() -> None:
    init_db()
    with SessionLocal() as db:
        users = UserRepository(db)
        for uid in SEED_USERS:
            users.get_or_create(uid)
        db.commit()

        service = SaleService(db)
        for user_id, brand, earning, external in SEED_SALES:
            service.create_sale(
                SaleCreate(
                    user_id=user_id, brand=brand, earning=earning, external_id=external
                )
            )
    print("Seed complete. Users:", ", ".join(SEED_USERS))


if __name__ == "__main__":
    main()
