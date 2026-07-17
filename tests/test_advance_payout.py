"""End-to-end tests for the advance-payout flow."""
from decimal import Decimal


def _create_sale(client, user_id="john_doe", brand="brand_1", earning="40.00", ext=None):
    body = {"user_id": user_id, "brand": brand, "earning": earning}
    if ext:
        body["external_id"] = ext
    r = client.post("/sales", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def test_advance_payout_is_10_percent(client):
    for i in range(3):
        _create_sale(client, ext=f"s{i}")

    r = client.post("/advance-payout", json={"user_id": "john_doe"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert Decimal(data["total_advance_credited"]) == Decimal("12.00")
    assert Decimal(data["wallet_balance"]) == Decimal("12.00")


def test_advance_payout_is_idempotent(client):
    _create_sale(client, ext="a")
    _create_sale(client, ext="b")

    r1 = client.post("/advance-payout", json={"user_id": "john_doe"})
    r2 = client.post("/advance-payout", json={"user_id": "john_doe"})
    assert Decimal(r1.json()["total_advance_credited"]) == Decimal("8.00")
    assert Decimal(r2.json()["total_advance_credited"]) == Decimal("0.00")

    wallet = client.get("/wallet", params={"user_id": "john_doe"}).json()
    assert Decimal(wallet["available_balance"]) == Decimal("8.00")


def test_sale_ingest_is_idempotent_by_external_id(client):
    s1 = _create_sale(client, ext="dup-1")
    s2 = _create_sale(client, ext="dup-1")
    assert s1["id"] == s2["id"]
