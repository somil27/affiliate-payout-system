"""API v1 router aggregation."""
from fastapi import APIRouter

from app.api.v1 import health, payouts, reconciliation, sales, transactions, wallet, withdrawals

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(sales.router)
api_router.include_router(payouts.router)
api_router.include_router(reconciliation.router)
api_router.include_router(withdrawals.router)
api_router.include_router(wallet.router)
api_router.include_router(transactions.router)
