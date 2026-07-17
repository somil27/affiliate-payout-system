# Payout Management Service

A production-grade FastAPI backend that manages **affiliate-sale advance payouts, reconciliation, wallet balances, and withdrawals** — implementing the SDE Intern assignment end-to-end.

Built with clean layered architecture, SOLID principles, database-enforced idempotency, structured logging, and a full test suite.

---

## Table of contents

1. [Features](#features)
2. [Tech stack](#tech-stack)
3. [Architecture](#architecture)
4. [Project layout](#project-layout)
5. [Database schema](#database-schema)
6. [Running locally](#running-locally)
7. [API reference](#api-reference)
8. [Sample requests](#sample-requests)
9. [Testing](#testing)
10. [Design decisions & trade-offs](#design-decisions--trade-offs)
11. [Future improvements](#future-improvements)

---

## Features

- **Sale ingestion** with per-user idempotency (`external_id`)
- **Advance payout** — credits 10 % of pending-sale earnings, safely idempotent under duplicate or concurrent calls
- **Reconciliation** of pending sales as `approved` / `rejected`, with correct wallet math for both cases
- **Wallet balance** tracked as an ACID-consistent aggregate with an append-only transaction log
- **Withdrawals** with a configurable 24-hour cooldown and idempotency-key support
- **Failed-payout recovery**: `failed` / `cancelled` / `rejected` withdrawals auto-credit the wallet and are re-triable
- **REST APIs** with Pydantic validation, structured JSON logging, request IDs, custom exception envelope
- **OpenAPI / Swagger** at `/docs`, ReDoc at `/redoc`
- **Pagination, filtering, sorting, search** on `/sales`, `/transactions`, `/withdrawals`
- **Health probe** at `/health`
- **Seed script** for local demos
- **11 pytest cases** covering the assignment's business rules

---

## Tech stack

| Layer          | Choice                          |
| -------------- | ------------------------------- |
| Language       | Python 3.11+                    |
| Framework      | FastAPI                         |
| ORM            | SQLAlchemy 2.x (typed mappings) |
| Validation     | Pydantic v2 + pydantic-settings |
| DB (default)   | SQLite (WAL, FK enforced)       |
| Migrations     | Alembic-ready (schema autoinit) |
| Tests          | pytest + FastAPI TestClient     |

Swap SQLite for Postgres by changing `DATABASE_URL` — no code changes required.

---

## Architecture

Strict **layered architecture** with a single direction of dependency:

```text
      HTTP  ─────────────► FastAPI Router (app/api/v1)
                                │  (validation only, no logic)
                                ▼
                       Service Layer (app/services)
                                │  (business rules, tx boundaries)
                                ▼
                    Repository Layer (app/repositories)
                                │  (query construction, no commits)
                                ▼
                          SQLAlchemy ORM
                                │
                                ▼
                             Database
```

- **Routers** own only HTTP concerns: parsing, status codes, response models.
- **Services** own business logic *and* the unit-of-work (`commit` / `rollback`). All money-touching operations lock the wallet row (`SELECT … FOR UPDATE`) and write an immutable `transactions` row.
- **Repositories** own query construction; they never commit.
- **Domain exceptions** (`app/core/exceptions.py`) are mapped to HTTP by a single middleware — the service layer stays HTTP-agnostic.

See [`docs/LLD.md`](docs/LLD.md) for the full low-level design, sequence diagrams, and ER diagram.

---

## Project layout

```text
payout-service/
├── app/
│   ├── api/v1/            # HTTP routers (thin)
│   ├── core/              # config, logging, exceptions
│   ├── database/          # engine, session, Base
│   ├── middleware/        # request-id, error handlers
│   ├── models/            # SQLAlchemy ORM + enums
│   ├── repositories/      # data access
│   ├── schemas/           # Pydantic DTOs
│   ├── services/          # business logic
│   └── main.py            # app factory
├── tests/                 # pytest suite
├── docs/LLD.md            # low-level design
├── main.py                # uvicorn entrypoint
├── seed.py                # demo seed data
├── requirements.txt
├── .env.example
└── README.md
```

---

## Database schema

```text
users ──┬── sales ──── advance_payouts
        │
        ├── wallets  (1:1)
        │
        ├── withdrawals ── withdrawal_history
        │
        └── transactions
```

See `docs/LLD.md` for the Mermaid ER diagram, constraints, and index list.

---

## Running locally

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. (Optional) seed demo data

```bash
python seed.py
```

### 3. Run

```bash
uvicorn main:app --reload
```

Open **http://localhost:8000/docs** for interactive Swagger UI.

---

## API reference

| Method | Path                       | Purpose                                              |
| ------ | -------------------------- | ---------------------------------------------------- |
| GET    | `/health`                  | Liveness probe                                       |
| POST   | `/sales`                   | Ingest a new sale (idempotent via `external_id`)     |
| GET    | `/sales`                   | List / search / paginate sales                       |
| POST   | `/advance-payout`          | Credit 10 % advance for eligible pending sales       |
| POST   | `/reconcile`               | Reconcile a batch of sales as approved/rejected      |
| POST   | `/withdraw`                | Request a withdrawal                                 |
| POST   | `/retry-withdrawal`        | Retry a failed/cancelled/rejected withdrawal         |
| POST   | `/withdrawals/status`      | Provider/admin callback to settle a withdrawal       |
| GET    | `/withdrawals`             | List a user's withdrawals                            |
| GET    | `/wallet?user_id=…`        | Get wallet balance                                   |
| GET    | `/transactions?user_id=…`  | List a user's wallet transactions                    |

All error responses follow the same envelope:

```json
{"code": "insufficient_funds", "message": "…", "request_id": "…"}
```

---

## Sample requests

Create three pending sales, credit an advance, then reconcile:

```bash
# 1. ingest three sales for john_doe
for i in 1 2 3; do
  curl -sX POST localhost:8000/sales -H 'content-type: application/json' \
    -d "{\"user_id\":\"john_doe\",\"brand\":\"brand_1\",\"earning\":\"40.00\",\"external_id\":\"s$i\"}"
done

# 2. advance payout (10 % of 120 = 12)
curl -sX POST localhost:8000/advance-payout \
  -H 'content-type: application/json' \
  -d '{"user_id":"john_doe"}'

# 3. reconcile: reject 1, approve 2  →  net adjustment 68
curl -sX POST localhost:8000/reconcile \
  -H 'content-type: application/json' \
  -d '{"items":[
        {"sale_id":1,"status":"rejected"},
        {"sale_id":2,"status":"approved"},
        {"sale_id":3,"status":"approved"}
      ]}'

# 4. wallet balance
curl -s 'localhost:8000/wallet?user_id=john_doe'

# 5. withdraw
curl -sX POST localhost:8000/withdraw \
  -H 'content-type: application/json' \
  -d '{"user_id":"john_doe","amount":"50.00","idempotency_key":"w-1"}'
```

---

## Testing

```bash
pytest -q
```

The suite covers:

- 10 % advance correctness and idempotency (including replay)
- Sale ingest deduplication by `external_id`
- Assignment example reconciliation math (`-4 + 36 + 36 = 68`)
- Reject on double reconciliation
- Withdrawal 24 h cooldown
- Failed → refund → retry lifecycle
- Withdrawal idempotency-key replay
- Insufficient funds rejection
- Health + OpenAPI availability

---

## Design decisions & trade-offs

**Why layered architecture?**
Each layer has a single responsibility and depends only on the layer below. That means the service layer is fully unit-testable without HTTP, and swapping SQLite for Postgres or FastAPI for another framework touches only the outer layers.

**Why the repository pattern?**
Isolates SQLAlchemy from business code. Services read like a domain description; the query language never leaks upward. Also lets us mock persistence for unit tests without spinning up a DB.

**Why explicit `SELECT … FOR UPDATE` on the wallet?**
Concurrent advance-payout jobs or a payout + withdrawal racing on the same wallet would otherwise overwrite balances. Row-level locking keeps money movement serializable per user without a global lock.

**Why idempotency at two layers?**
- Application-level: `list_pending_without_advance` short-circuits already-paid sales for the common case.
- Database-level: `UNIQUE(sale_id)` on `advance_payouts` guarantees safety even if two workers race past the check simultaneously — the loser gets `IntegrityError`, which we swallow inside a SAVEPOINT so the rest of the batch still succeeds.

**Why an immutable `transactions` table?**
It is the audit source of truth. The wallet balance is a materialised aggregate that must equal `SUM(credits) − SUM(debits)` at all times; the log makes reconciliation and forensics trivial.

**Why allow the wallet to go negative on rejected sales?**
If the user already withdrew the advance and the sale is later rejected, the money is gone. Marking the wallet negative preserves accounting integrity and blocks further withdrawals until the debt is worked off, which is the correct product behaviour.

**Trade-offs**

- SQLite `FOR UPDATE` is a no-op — locking still works because SQLite serialises writers globally, but Postgres is recommended for real workloads.
- Cooldown is enforced at the service layer, not with a DB unique constraint on `(user_id, day)`, so it stays configurable via env.
- Retries deliberately skip the cooldown: the original attempt already consumed it and the reversal put the money back — treating a retry as a "new" withdrawal would lock users out for a whole day after any provider failure.

---

## Future improvements

- Async SQLAlchemy + `asyncpg` for higher concurrency
- Idempotency-key store as a first-class table (currently opportunistic)
- Outbox pattern + background worker for real payout provider integration
- Alembic migrations wired to CI (schema is currently auto-created)
- OpenTelemetry tracing spans across layers
- Role-based auth (JWT) — users vs admin (reconciliation is admin-only)
- Rate limiting per-IP on write endpoints
- Prometheus `/metrics` endpoint
