from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.exceptions import InvalidStateError, NotFoundError
from app.models.enums import SaleStatus, TransactionDirection, TransactionType
from app.repositories.advance_payout_repository import AdvancePayoutRepository
from app.repositories.sale_repository import SaleRepository
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.wallet_repository import WalletRepository
from app.schemas.sale import ReconcileItem, ReconcileResponse

logger = logging.getLogger(__name__)


class ReconciliationService:
    """Move Pending sales to Approved / Rejected and settle wallet impact.

    Approved: credit remaining (earning - advance) to wallet.
    Rejected: reverse the advance from the wallet (allowed to go negative,
              because the money already left as an advance payout).
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.sales = SaleRepository(db)
        self.wallets = WalletRepository(db)
        self.advances = AdvancePayoutRepository(db)
        self.transactions = TransactionRepository(db)

    def reconcile(self, items: list[ReconcileItem]) -> ReconcileResponse:
        if not items:
            raise InvalidStateError("No sales to reconcile")

        # All items must belong to the same user (per-user wallet lock).
        # Deduce and validate that up front.
        sale_ids = [i.sale_id for i in items]
        first = self.sales.get(sale_ids[0])
        if first is None:
            raise NotFoundError(f"Sale {sale_ids[0]} not found")
        user_id = first.user_id

        wallet = self.wallets.get_locked(user_id)

        approved_count = rejected_count = 0
        credited_total = Decimal("0.00")
        reversed_total = Decimal("0.00")

        for item in items:
            sale = self.sales.get_locked(item.sale_id)
            if sale is None:
                raise NotFoundError(f"Sale {item.sale_id} not found")
            if sale.user_id != user_id:
                raise InvalidStateError(
                    "All sales in a reconciliation batch must belong to the same user"
                )
            if sale.status != SaleStatus.PENDING.value:
                raise InvalidStateError(
                    f"Sale {sale.id} already reconciled as '{sale.status}'"
                )

            advance = self.advances.get_by_sale(sale.id)
            advance_amount = advance.amount if advance else Decimal("0.00")

            if item.status == SaleStatus.APPROVED:
                remainder = (sale.earning - advance_amount).quantize(Decimal("0.01"))
                if remainder > 0:
                    new_balance = self.wallets.credit(wallet, remainder)
                    self.wallets.add_lifetime(wallet, sale.earning)
                    self.transactions.record(
                        user_id=user_id,
                        type_=TransactionType.RECONCILE_APPROVED,
                        direction=TransactionDirection.CREDIT,
                        amount=remainder,
                        balance_after=new_balance,
                        reference_type="sale",
                        reference_id=sale.id,
                        description=(
                            f"Approved sale {sale.id}: earning {sale.earning} - "
                            f"advance {advance_amount}"
                        ),
                    )
                    credited_total += remainder
                sale.status = SaleStatus.APPROVED.value
                approved_count += 1

            else:  # REJECTED
                if advance_amount > 0:
                    # Allow negative: the user may have already withdrawn part
                    # of the advance; a negative balance blocks further
                    # withdrawals until they refund or earn it back.
                    new_balance = self.wallets.debit(
                        wallet, advance_amount, allow_negative=True
                    )
                    self.transactions.record(
                        user_id=user_id,
                        type_=TransactionType.RECONCILE_REJECTED,
                        direction=TransactionDirection.DEBIT,
                        amount=advance_amount,
                        balance_after=new_balance,
                        reference_type="sale",
                        reference_id=sale.id,
                        description=(
                            f"Rejected sale {sale.id}: reverse advance of {advance_amount}"
                        ),
                    )
                    reversed_total += advance_amount
                sale.status = SaleStatus.REJECTED.value
                rejected_count += 1

            sale.reconciled_at = datetime.now(timezone.utc)

        self.db.commit()
        self.db.refresh(wallet)
        logger.info(
            "reconciliation.completed",
            extra={
                "user_id": user_id,
                "approved": approved_count,
                "rejected": rejected_count,
                "credited": str(credited_total),
                "reversed": str(reversed_total),
            },
        )
        return ReconcileResponse(
            user_id=user_id,
            approved_count=approved_count,
            rejected_count=rejected_count,
            credited_amount=credited_total,
            reversed_amount=reversed_total,
            net_adjustment=(credited_total - reversed_total).quantize(Decimal("0.01")),
            wallet_balance=wallet.available_balance,
        )
