from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import User, Wallet


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def get_or_create(self, user_id: str) -> User:
        """Return the user; create it (and an empty wallet) on first sight.

        Users are commonly created out-of-band; for the scope of this service
        we create them lazily so ingesting a sale for a new user just works.
        """
        user = self.get(user_id)
        if user is not None:
            return user
        user = User(id=user_id)
        self.db.add(user)
        self.db.flush()
        wallet = Wallet(user_id=user.id)
        self.db.add(wallet)
        self.db.flush()
        return user

    def list(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        stmt = select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt))
