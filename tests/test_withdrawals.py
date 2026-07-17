"""Withdrawal cooldown, failure recovery, retry."""
from decimal import Decimal


def _prepare_wallet(client, amount=Decimal("100.00")):
    client.post(
        "/sales",
        json={"user_id": "john_doe", "brand": "brand_1", "earning": str(amount * 10), "external_id": "w1"},
    )
    client.post("/advance-payout", json={"user_id": "john_doe"})
    # After 10% advance: wallet = amount


def test_withdrawal_cooldown_blocks_second_request(client):
    _prepare_wallet(client)
    r1 = client.post("/withdraw", json={"user_id": "john_doe", "amount": "10.00"})
    assert r1.status_code == 201, r1.text
    r2 = client.post("/withdraw", json={"user_id": "john_doe", "amount": "10.00"})
    assert r2.status_code == 429


def test_failed_withdrawal_is_refunded_and_retryable(client):
    _prepare_wallet(client)
    r1 = client.post("/withdraw", json={"user_id": "john_doe", "amount": "10.00"})
    withdrawal_id = r1.json()["id"]

    # Provider callback: failed
    r_fail = client.post(
        "/withdrawals/status",
        json={"withdrawal_id": withdrawal_id, "status": "failed", "reason": "bank down"},
    )
    assert r_fail.status_code == 200
    assert r_fail.json()["status"] == "failed"

    wallet = client.get("/wallet", params={"user_id": "john_doe"}).json()
    assert Decimal(wallet["available_balance"]) == Decimal("100.00")  # refunded

    # Retry does not need to wait for cooldown
    r_retry = client.post("/retry-withdrawal", json={"withdrawal_id": withdrawal_id})
    assert r_retry.status_code == 201
    assert r_retry.json()["retried_from_id"] == withdrawal_id


def test_withdrawal_idempotency_key(client):
    _prepare_wallet(client)
    body = {"user_id": "john_doe", "amount": "10.00", "idempotency_key": "abc-123"}
    r1 = client.post("/withdraw", json=body)
    r2 = client.post("/withdraw", json=body)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_insufficient_funds_rejected(client):
    _prepare_wallet(client)
    r = client.post("/withdraw", json={"user_id": "john_doe", "amount": "9999.00"})
    assert r.status_code == 409
