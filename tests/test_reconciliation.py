"""Reconciliation math must match the assignment example."""
from decimal import Decimal


def _seed_three_sales(client):
    ids = []
    for i in range(3):
        r = client.post(
            "/sales",
            json={"user_id": "john_doe", "brand": "brand_1", "earning": "40.00", "external_id": f"r{i}"},
        )
        ids.append(r.json()["id"])
    client.post("/advance-payout", json={"user_id": "john_doe"})
    return ids


def test_reconcile_matches_assignment_example(client):
    ids = _seed_three_sales(client)
    # 1 rejected, 2 approved -> total payout = -4 + 36 + 36 = 68; wallet already had 12 advance
    r = client.post(
        "/reconcile",
        json={
            "items": [
                {"sale_id": ids[0], "status": "rejected"},
                {"sale_id": ids[1], "status": "approved"},
                {"sale_id": ids[2], "status": "approved"},
            ]
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert Decimal(data["credited_amount"]) == Decimal("72.00")   # 36 + 36
    assert Decimal(data["reversed_amount"]) == Decimal("4.00")
    assert Decimal(data["net_adjustment"]) == Decimal("68.00")
    # Wallet = 12 (advance) + 72 (approved remainders) - 4 (reversal) = 80
    # But total user is entitled to = 68 + 12 already received... no:
    # Actually final wallet available_balance = 12 + 72 - 4 = 80,
    # of which 12 was already advance. Net final payout figure is 68 for the batch,
    # matching the assignment. Wallet has 80 available which is 68 + 12 offset only
    # for the retained advance; verify by absolute check:
    assert Decimal(data["wallet_balance"]) == Decimal("80.00")


def test_double_reconcile_is_rejected(client):
    ids = _seed_three_sales(client)
    client.post("/reconcile", json={"items": [{"sale_id": ids[0], "status": "approved"}]})
    r = client.post("/reconcile", json={"items": [{"sale_id": ids[0], "status": "approved"}]})
    assert r.status_code == 409
