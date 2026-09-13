
# Finora Backend

Flask + PostgreSQL backend for Finora.

## Setup

1. Create a PostgreSQL database:

```sql
CREATE DATABASE finora;
```

2. Create a virtual environment.

Windows PowerShell:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Copy `.env.example` to `.env` and set your PostgreSQL password, SECRET_KEY and JWT_SECRET_KEY.

5. Initialize the database:

```bash
flask db init
flask db migrate -m "Initial Finora schema"
flask db upgrade
```

Run `flask db init` only once.

6. Start the API:

```bash
python run.py
```

Health endpoint:

```text
GET http://127.0.0.1:5000/api/health
```

## Main API groups

- `/api/auth`
- `/api/users`
- `/api/accounts`
- `/api/categories`
- `/api/transactions`
- `/api/budgets`
- `/api/goals`
- `/api/bills`
- `/api/analytics`
- `/api/notifications`

All routes except register, login and health are JWT-protected.
