
from datetime import date, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from ..extensions import db
from ..models import (
    Account,
    Transaction,
    Budget,
    Bill,
    Goal,
    Notification,
    Category,
)
from ..services.finance import (
    totals,
    month_bounds,
    reconcile,
)
from .common import uid
from .budgets import serialize as budget_dict


bp = Blueprint("analytics", __name__)


def scoped_accounts(user):
    return (
        Account.query
        .filter_by(user_id=user, is_archived=False)
        .order_by(Account.created_at.desc())
        .all()
    )


def currency_total(user):
    accounts = scoped_accounts(user)
    currencies = {a.currency for a in accounts}

    if len(currencies) > 1:
        return None

    return round(
        sum(float(a.balance) for a in accounts),
        2,
    )


def monthly_statistics(user, year, month):
    """
    Calculate statistics for one user's transactions
    within the selected calendar month.
    """
    start, end = month_bounds(year, month)

    base = Transaction.query.filter(
        Transaction.user_id == user,
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end,
    )

    transaction_count = base.count()

    expense_query = base.filter(
        Transaction.transaction_type == "expense"
    )

    expense_count = expense_query.count()

    expense_total = (
        db.session.query(func.sum(Transaction.amount))
        .filter(
            Transaction.user_id == user,
            Transaction.transaction_type == "expense",
            Transaction.transaction_date >= start,
            Transaction.transaction_date < end,
        )
        .scalar()
    )

    expense_total = float(expense_total or 0)

    average_expense = (
        expense_total / expense_count
        if expense_count > 0
        else 0
    )

    largest_expense = (
        expense_query
        .order_by(
            Transaction.amount.desc(),
            Transaction.id.desc(),
        )
        .first()
    )

    return {
        "transaction_count": transaction_count,
        "expense_count": expense_count,
        "average_expense": round(average_expense, 2),
        "largest_expense": (
            largest_expense.to_dict()
            if largest_expense
            else None
        ),
    }


@bp.get("/analytics/dashboard")
@jwt_required()
def dashboard():
    user = uid()
    today = date.today()

    income, expenses = totals(
        user,
        today.year,
        today.month,
    )

    accounts = scoped_accounts(user)
    balance = currency_total(user)

    bills = (
        Bill.query
        .filter(
            Bill.user_id == user,
            Bill.is_active.is_(True),
            Bill.next_due_date >= today,
            Bill.next_due_date <= today + timedelta(days=30),
        )
        .order_by(Bill.next_due_date)
        .all()
    )

    upcoming = sum(float(b.amount) for b in bills)

    budgets = [
        budget_dict(b)
        for b in Budget.query.filter_by(
            user_id=user,
            month=today.month,
            year=today.year,
        ).all()
    ]

    spent = sum(b["spent"] for b in budgets)
    budgeted = sum(b["amount"] for b in budgets)

    recent_transactions = (
        Transaction.query
        .filter_by(user_id=user)
        .order_by(
            Transaction.transaction_date.desc(),
            Transaction.id.desc(),
        )
        .limit(5)
        .all()
    )

    stats = monthly_statistics(
        user,
        today.year,
        today.month,
    )

    return jsonify(
        available_balance=balance,
        balance_currency=(
            accounts[0].currency
            if accounts and balance is not None
            else None
        ),
        mixed_currencies=balance is None,
        safe_to_spend=(
            max(balance - upcoming, 0)
            if balance is not None
            else None
        ),
        income_this_month=income,
        expenses_this_month=expenses,
        net_cash_flow=income - expenses,
        savings_rate=(
            round(
                (income - expenses) / income * 100,
                1,
            )
            if income > 0
            else None
        ),
        upcoming_bills=upcoming,
        transaction_count=stats["transaction_count"],
        unread_notifications=(
            Notification.query
            .filter_by(user_id=user, is_read=False)
            .count()
        ),
        recent_transactions=[
            transaction.to_dict()
            for transaction in recent_transactions
        ],
        accounts=[
            account.to_dict()
            for account in accounts[:4]
        ],
        upcoming_bill_items=[
            dict(
                **bill.to_dict(),
                days_until_due=(
                    bill.next_due_date - today
                ).days,
            )
            for bill in bills[:4]
        ],
        goals=[
            goal.to_dict()
            for goal in Goal.query.filter_by(
                user_id=user,
                is_completed=False,
            ).limit(3)
        ],
        budgets=budgets[:4],
        budget_summary={
            "total_budget": budgeted,
            "spent": spent,
            "remaining": budgeted - spent,
            "percentage": (
                round(spent / budgeted * 100, 1)
                if budgeted
                else 0
            ),
        },
    )


@bp.get("/analytics/summary")
@jwt_required()
def summary():
    today = date.today()
    user = uid()

    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))

    income, expenses = totals(user, year, month)

    net = income - expenses

    savings_rate = (
        round(net / income * 100, 1)
        if income > 0
        else None
    )

    return jsonify(
        income=income,
        expenses=expenses,
        net=net,
        net_cash_flow=net,
        savings_rate=savings_rate,
        available_balance=currency_total(user),
    )


@bp.get("/analytics/monthly-trend")
@jwt_required()
def trend():
    today = date.today()
    user = uid()
    rows = []

    for offset in range(5, -1, -1):
        n = today.year * 12 + today.month - 1 - offset

        year = n // 12
        month = n % 12 + 1

        income, expenses = totals(
            user,
            year,
            month,
        )

        rows.append({
            "month": f"{year}-{month:02d}",
            "income": income,
            "expenses": expenses,
            "net": income - expenses,
        })

    return jsonify(
        trend=rows,
        monthly_trend=rows,
    )


@bp.get("/analytics/spending-by-category")
@jwt_required()
def spending():
    today = date.today()
    user = uid()

    year = int(request.args.get("year", today.year))
    month = int(request.args.get("month", today.month))

    start, end = month_bounds(year, month)

    rows = (
        db.session.query(
            Category.id,
            Category.name,
            func.sum(Transaction.amount),
        )
        .join(
            Transaction,
            Transaction.category_id == Category.id,
        )
        .filter(
            Transaction.user_id == user,
            Category.user_id == user,
            Transaction.transaction_type == "expense",
            Transaction.transaction_date >= start,
            Transaction.transaction_date < end,
        )
        .group_by(
            Category.id,
            Category.name,
        )
        .all()
    )

    total_spending = sum(
        float(amount or 0)
        for _, _, amount in rows
    )

    categories = []

    for category_id, name, amount in rows:
        amount = float(amount or 0)

        percentage = (
            round(amount / total_spending * 100, 1)
            if total_spending > 0
            else 0
        )

        categories.append({
            "category_id": category_id,
            "category": name,
            "name": name,
            "amount": amount,
            "spent": amount,
            "total": amount,
            "percentage": percentage,
        })

    categories.sort(
        key=lambda item: item["amount"],
        reverse=True,
    )

    return jsonify(
        categories=categories,
        spending_by_category=categories,
    )


@bp.get("/analytics/accounts")
@jwt_required()
def accounts():
    user = uid()

    return jsonify(
        accounts=[
            account.to_dict()
            for account in scoped_accounts(user)
        ],
        total=currency_total(user),
    )


@bp.get("/analytics/insights")
@jwt_required()
def insights():
    today = date.today()
    user = uid()

    income, expenses = totals(
        user,
        today.year,
        today.month,
    )

    stats = monthly_statistics(
        user,
        today.year,
        today.month,
    )

    return jsonify(
        transaction_count=stats["transaction_count"],
        expense_count=stats["expense_count"],
        average_expense=stats["average_expense"],
        largest_expense=stats["largest_expense"],
        insights=[
            {
                "title": "Monthly cash flow",
                "message": (
                    f"Income {income:.2f}; "
                    f"expenses {expenses:.2f}; "
                    f"net {income - expenses:.2f}."
                ),
            }
        ],
    )


@bp.get("/analytics/reconcile")
@jwt_required()
def audit():
    rows = reconcile(uid())

    return jsonify(
        accounts=rows,
        all_match=all(
            row["matches"]
            for row in rows
        ),
    )
