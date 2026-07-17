from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Withdrawal, WithdrawalHistory
from app.models.enums import WithdrawalStatus


class WithdrawalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, withdrawal_id: int) -> Withdrawal | None:
        return self.db.get(Withdrawal, withdrawal_id)

    def get_by_idempotency(self, key: str) -> Withdrawal | None:
        stmt = select(Withdrawal).where(Withdrawal.idempotency_key == key)
        return self.db.scalars(stmt).first()

    def add(self, withdrawal: Withdrawal) -> Withdrawal:
        self.db.add(withdrawal)
        self.db.flush()
        return withdrawal

    def add_history(
        self,
        withdrawal: Withdrawal,
        *,
        from_status: str | None,
        to_status: str,
        note: str | None = None,
    ) -> WithdrawalHistory:
        entry = WithdrawalHistory(
            withdrawal_id=withdrawal.id,
            from_status=from_status,
            to_status=to_status,
            note=note,
        )
        self.db.add(entry)
        self.db.flush()
        return entry

    def latest_non_failed_within(
        self, user_id: str, *, since: datetime
    ) -> Withdrawal | None:
        """Most recent PENDING/SUCCESS withdrawal in the cooldown window.

        Failed/cancelled/rejected withdrawals do not count against cooldown –
        the money never actually left the system.
        """
        blocking_states = [WithdrawalStatus.PENDING.value, WithdrawalStatus.SUCCESS.value]
        stmt = (
            select(Withdrawal)
            .where(
                Withdrawal.user_id == user_id,
                Withdrawal.status.in_(blocking_states),
                Withdrawal.created_at >= since,
            )
            .order_by(Withdrawal.created_at.desc())
            .limit(1)
        )
        return self.db.scalars(stmt).first()

    def list_for_user(
        self, user_id: str, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[Withdrawal], int]:
        base = select(Withdrawal).where(Withdrawal.user_id == user_id)
        total = self.db.scalar(select(func.count()).select_from(base.subquery())) or 0
        stmt = base.order_by(Withdrawal.created_at.desc()).limit(limit).offset(offset)
        return list(self.db.scalars(stmt)), int(total)
