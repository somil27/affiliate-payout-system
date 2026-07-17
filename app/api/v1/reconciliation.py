from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import ReconcileRequest, ReconcileResponse
from app.services.reconciliation_service import ReconciliationService

router = APIRouter(tags=["reconciliation"])


@router.post(
    "/reconcile",
    response_model=ReconcileResponse,
    summary="Reconcile a batch of sales as approved/rejected",
)
def reconcile(payload: ReconcileRequest, db: Session = Depends(get_db)) -> ReconcileResponse:
    return ReconciliationService(db).reconcile(payload.items)
