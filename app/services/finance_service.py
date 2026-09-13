
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy import func
from app.extensions import db
from app.models import Account, Bill, Transaction

def account_total(user_id):
    total = db.session.query(func.coalesce(func.sum(Account.balance), 0)).filter(
        Account.user_id == user_id, Account.is_archived.is_(False)
    ).scalar()
    return float(total or 0)

def month_bounds(year, month):
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    return start, end

def month_totals(user_id, year, month):
    start, end = month_bounds(year, month)
    def total_for(kind):
        return float(db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
            Transaction.user_id == user_id,
            Transaction.transaction_type == kind,
            Transaction.transaction_date >= start,
            Transaction.transaction_date < end,
        ).scalar() or 0)
    return total_for("income"), total_for("expense")

def upcoming_bills_total(user_id, days=30):
    today, cutoff = date.today(), date.today() + timedelta(days=days)
    total = db.session.query(func.coalesce(func.sum(Bill.amount), 0)).filter(
        Bill.user_id == user_id,
        Bill.is_active.is_(True),
        Bill.next_due_date >= today,
        Bill.next_due_date <= cutoff,
    ).scalar()
    return float(total or 0)

def safe_to_spend(user_id):
    balance = account_total(user_id)
    bills = upcoming_bills_total(user_id, 30)
    return {"balance": round(balance, 2), "upcoming_bills": round(bills, 2), "safe_to_spend": round(max(balance - bills, 0), 2)}

def apply_transaction_to_accounts(transaction, reverse=False):
    multiplier = Decimal("-1") if reverse else Decimal("1")
    amount = Decimal(transaction.amount)
    source = Account.query.filter_by(id=transaction.account_id, user_id=transaction.user_id).first()
    if not source:
        raise ValueError("Source account not found.")

    if transaction.transaction_type == "expense":
        source.balance -= multiplier * amount
    elif transaction.transaction_type == "income":
        source.balance += multiplier * amount
    elif transaction.transaction_type == "transfer":
        destination = Account.query.filter_by(id=transaction.destination_account_id, user_id=transaction.user_id).first()
        if not destination:
            raise ValueError("Destination account not found.")
        source.balance -= multiplier * amount
        destination.balance += multiplier * amount
