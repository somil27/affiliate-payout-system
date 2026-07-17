"""Domain enum values as plain string constants for portability."""
from __future__ import annotations

from enum import Enum


class SaleStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class WithdrawalStatus(str, Enum):
    PENDING = "pending"          # created, not yet settled by payout provider
    SUCCESS = "success"          # money left our system
    FAILED = "failed"            # provider returned failure
    CANCELLED = "cancelled"      # user/admin cancelled
    REJECTED = "rejected"        # provider/compliance rejected

    @classmethod
    def failure_states(cls) -> set["WithdrawalStatus"]:
        return {cls.FAILED, cls.CANCELLED, cls.REJECTED}


class TransactionType(str, Enum):
    ADVANCE_PAYOUT = "advance_payout"
    RECONCILE_APPROVED = "reconcile_approved"
    RECONCILE_REJECTED = "reconcile_rejected"
    WITHDRAWAL = "withdrawal"
    WITHDRAWAL_REVERSAL = "withdrawal_reversal"


class TransactionDirection(str, Enum):
    CREDIT = "credit"
    DEBIT = "debit"
