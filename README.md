# Finora Backend — Standalone V2

Complete independent Flask REST backend with PostgreSQL, JWT auth, account/transaction CRUD, budgets, goals, bills, notifications, analytics, reconciliation and tests.

## 1. Setup (Ubuntu/Linux)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with a **new** database name, database user credentials, and a randomly generated JWT secret. Example secret generator:

```bash
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Create a fresh PostgreSQL database (example as a PostgreSQL admin):

```sql
CREATE USER finora_v2_user WITH PASSWORD 'REPLACE_WITH_A_NEW_STRONG_PASSWORD';
CREATE DATABASE finora_v2 OWNER finora_v2_user;
```

Update `DATABASE_URL` accordingly. Never commit `.env`.

## 2. Initialize database

```bash
flask --app run.py db init
flask --app run.py db migrate -m 'Initial schema'
flask --app run.py db upgrade
```

Run `db init` **only once**. On subsequent model changes, use `db migrate` and `db upgrade`.

## 3. Run and test

```bash
python3 run.py
# Separate terminal:
python3 -m pytest -v
```

API base URL: `http://127.0.0.1:5000/api`

## Main endpoints

- `POST /auth/register`, `/auth/login`, `/auth/refresh`, `GET /auth/me`
- `GET, POST /accounts`; `GET, PATCH, DELETE /accounts/<id>`
- `GET, POST /categories`
- `GET, POST /transactions`; `GET, PATCH, DELETE /transactions/<id>`
- `GET, POST /budgets`; `PATCH, DELETE /budgets/<id>`
- `GET, POST /goals`; `GET, PATCH, DELETE /goals/<id>`; `GET, POST /goals/<id>/contributions`
- `GET, POST /bills`; `PATCH, DELETE /bills/<id>`; `POST /bills/<id>/pay`
- `GET /notifications`; `POST /notifications/read-all`; `DELETE /notifications/clear-read`
- `GET /analytics/dashboard`, `/summary`, `/monthly-trend`, `/spending-by-category`, `/accounts`, `/insights`, `/reconcile`
- `GET /health`, `GET /settings`, `PATCH /settings/profile`, `POST /settings/password`

Authenticated endpoints require `Authorization: Bearer <access token>`.

## Financial rules

- All amounts use `Decimal` with max 2 fractional digits and database `NUMERIC(14,2)`.
- Every account has an immutable opening balance; transactions adjust the current balance.
- Editing a transaction reverses its old effects and applies its new effects in a single DB transaction.
- Account rows are locked in stable ID order during writes on PostgreSQL.
- Cross-currency transfers are rejected; accounts with different currencies cannot be meaningfully summed. Dashboard `available_balance` is `null` for mixed currencies. Frontend must display an appropriate warning rather than treating null as zero.
- `Idempotency-Key` header is supported for creating transactions; use a new UUID per intended creation, and reuse it only for retries.
- Bills `pay` advances the due date **without creating an expense**.
- Goal contributions track progress **without moving account money**.
- Reconciliation endpoint reports stored vs calculated balances, without modifying records.

## Frontend compatibility notes

This is a **fresh backend**, not an exact byte-for-byte replica of the old API. The major route names are preserved, but some response shapes and action paths may differ from your current React frontend. Check Network requests and adapt React API calls before switching permanently.

`GET /analytics/dashboard` returns `available_balance: null` if there are multiple active account currencies. That is intentional; never silently sum currencies.

## Production limitations / remaining work

This is a substantial runnable development backend, **not a certified production-ready financial system**. Before public launch add full integration/concurrency tests on PostgreSQL, auth token revocation and password-reset flow, backup/restore drills, monitoring, hardened error handling, API pagination, robust input schema validation, notification scheduling, and a complete privacy/security audit. Rate limiting uses the default in-memory store; replace it with Redis in production.
