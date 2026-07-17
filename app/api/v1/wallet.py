from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import WalletRead
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get(
    "",
    response_model=WalletRead,
    summary="Get a user's wallet balance",
)
def get_wallet(user_id: str = Query(..., min_length=1), db: Session = Depends(get_db)) -> WalletRead:
    wallet = WalletService(db).get_wallet(user_id)
    return WalletRead.model_validate(wallet)
