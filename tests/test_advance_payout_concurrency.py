"""Concurrency tests for POST /advance-payout.

These reproduce the race between two simultaneous advance-payout requests
for the same user: both read the wallet, both try to credit it, and one of
them used to lose to sqlalchemy.orm.exc.StaleDataError on the optimistic
`version` column and bubble up as an HTTP 500. The fix must make both
requests succeed (or return a well-formed 200/409 — never a raw 500), pay
each sale's advance exactly once, and leave the wallet balance correct.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal


def _create_sale(client, ext, user_id="john_doe", earning="40.00"):
    r = client.post(
        "/sales",
        json={"user_id": user_id, "brand": "brand_1", "earning": earning, "external_id": ext},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_concurrent_advance_payout_requests_never_500_and_pay_once(client):
    n_sales = 10
    for i in range(n_sales):
        _create_sale(client, ext=f"c{i}")

    def call():
        return client.post("/advance-payout", json={"user_id": "john_doe"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(call)
        f2 = pool.submit(call)
        r1, r2 = f1.result(), f2.result()

    # Never a raw 500 — either a clean success or a well-formed 409 to retry.
    assert r1.status_code in (200, 409), r1.text
    assert r2.status_code in (200, 409), r2.text

    # Each sale's 10% advance (4.00) must be credited exactly once in total,
    # split across the two responses however the race resolves.
    expected_total = (Decimal("40.00") * Decimal("0.10")) * n_sales

    def credited(resp):
        return Decimal(resp.json()["total_advance_credited"]) if resp.status_code == 200 else Decimal("0.00")

    total_credited_across_responses = credited(r1) + credited(r2)
    assert total_credited_across_responses == expected_total

    wallet = client.get("/wallet", params={"user_id": "john_doe"}).json()
    assert Decimal(wallet["available_balance"]) == expected_total


def test_concurrent_advance_payout_is_still_idempotent_after_race(client):
    """A third call after the race settles must report nothing left to pay."""
    for i in range(5):
        _create_sale(client, ext=f"d{i}")

    def call():
        return client.post("/advance-payout", json={"user_id": "john_doe"})

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(call)
        f2 = pool.submit(call)
        f1.result(), f2.result()

    r3 = client.post("/advance-payout", json={"user_id": "john_doe"})
    assert r3.status_code == 200, r3.text
    assert Decimal(r3.json()["total_advance_credited"]) == Decimal("0.00")
    assert all(s["already_paid"] for s in r3.json()["sales"])