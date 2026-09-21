from datetime import date, datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from app.extensions import db

from app.models import (
    Account,
    Bill,
    Budget,
    Category,
    Goal,
    Notification,
    Transaction,
)

from app.services.finance_service import (
    account_total,
    month_bounds,
    month_totals,
    safe_to_spend,
    upcoming_bills_total,
)

from app.utils.auth import current_user


analytics_bp = Blueprint(
    "analytics",
    __name__,
)


# =========================================================
# HELPERS
# =========================================================

def valid_period(year, month):
    return (
        2000 <= year <= 2100
        and 1 <= month <= 12
    )


def get_period():
    now = datetime.utcnow()

    try:
        year = int(
            request.args.get(
                "year",
                now.year,
            )
        )

        month = int(
            request.args.get(
                "month",
                now.month,
            )
        )

    except (TypeError, ValueError):
        return None, None

    if not valid_period(
        year,
        month,
    ):
        return None, None

    return year, month


def shift_month(
    year,
    month,
    offset,
):
    month_index = (
        year * 12
        + month
        - 1
        + offset
    )

    shifted_year = (
        month_index // 12
    )

    shifted_month = (
        month_index % 12
        + 1
    )

    return (
        shifted_year,
        shifted_month,
    )


def percent_change(
    current,
    previous,
):
    current = float(
        current or 0
    )

    previous = float(
        previous or 0
    )

    if previous == 0:
        if current == 0:
            return 0

        return None

    return round(
        (
            (
                current
                - previous
            )
            / previous
        )
        * 100,
        1,
    )


def savings_rate(
    income,
    expenses,
):
    income = float(
        income or 0
    )

    expenses = float(
        expenses or 0
    )

    if income <= 0:
        return 0

    return round(
        (
            (
                income
                - expenses
            )
            / income
        )
        * 100,
        1,
    )


# =========================================================
# DASHBOARD
# =========================================================

@analytics_bp.get(
    "/dashboard"
)
@jwt_required()
def dashboard():
    user = current_user()

    now = datetime.utcnow()
    today = date.today()

    # -----------------------------------------------------
    # CURRENT MONTH
    # -----------------------------------------------------

    month_start, month_end = (
        month_bounds(
            now.year,
            now.month,
        )
    )

    income, expenses = (
        month_totals(
            user.id,
            now.year,
            now.month,
        )
    )

    income = float(
        income or 0
    )

    expenses = float(
        expenses or 0
    )

    net_cash_flow = (
        income
        - expenses
    )

    current_savings_rate = (
        savings_rate(
            income,
            expenses,
        )
    )

    # -----------------------------------------------------
    # BALANCE + SAFE TO SPEND
    # -----------------------------------------------------

    available_balance = (
        account_total(
            user.id
        )
    )

    safe = safe_to_spend(
        user.id
    )

    upcoming_total = (
        upcoming_bills_total(
            user.id,
            30,
        )
    )

    # -----------------------------------------------------
    # RECENT TRANSACTIONS
    # -----------------------------------------------------

    recent_transactions = (
        Transaction.query
        .filter_by(
            user_id=user.id
        )
        .order_by(
            Transaction
            .transaction_date
            .desc()
        )
        .limit(5)
        .all()
    )

    # -----------------------------------------------------
    # MONTHLY TRANSACTION COUNT
    # -----------------------------------------------------

    transaction_count = (
        Transaction.query
        .filter(
            Transaction.user_id
            == user.id,

            Transaction.transaction_date
            >= month_start,

            Transaction.transaction_date
            < month_end,
        )
        .count()
    )

    # -----------------------------------------------------
    # ACCOUNTS
    # -----------------------------------------------------

    accounts = (
        Account.query
        .filter_by(
            user_id=user.id,
            is_archived=False,
        )
        .order_by(
            Account.is_default.desc(),
            Account.created_at.asc(),
        )
        .limit(4)
        .all()
    )

    account_items = [
        account.to_dict()
        for account in accounts
    ]

    # -----------------------------------------------------
    # UPCOMING BILLS
    # -----------------------------------------------------

    bill_cutoff = (
        today
        + timedelta(days=30)
    )

    upcoming_bills = (
        Bill.query
        .filter(
            Bill.user_id
            == user.id,

            Bill.is_active.is_(True),

            Bill.next_due_date
            >= today,

            Bill.next_due_date
            <= bill_cutoff,
        )
        .order_by(
            Bill.next_due_date.asc()
        )
        .limit(4)
        .all()
    )

    bill_items = []

    for bill in upcoming_bills:
        bill_data = (
            bill.to_dict()
        )

        bill_data[
            "days_until_due"
        ] = (
            bill.next_due_date
            - today
        ).days

        bill_items.append(
            bill_data
        )

    # -----------------------------------------------------
    # ACTIVE GOALS
    # -----------------------------------------------------

    goals = (
        Goal.query
        .filter(
            Goal.user_id
            == user.id,

            Goal.is_completed
            .is_(False),
        )
        .order_by(
            Goal.target_date
            .asc()
            .nullslast(),

            Goal.created_at.asc(),
        )
        .limit(3)
        .all()
    )

    goal_items = [
        goal.to_dict()
        for goal in goals
    ]

    # -----------------------------------------------------
    # CURRENT MONTH BUDGETS
    # -----------------------------------------------------

    budgets = (
        Budget.query
        .filter_by(
            user_id=user.id,
            month=now.month,
            year=now.year,
        )
        .all()
    )

    budget_items = []

    total_budget = 0
    total_budget_spent = 0

    for budget in budgets:

        spent = (
            db.session.query(
                func.coalesce(
                    func.sum(
                        Transaction.amount
                    ),
                    0,
                )
            )
            .filter(
                Transaction.user_id
                == user.id,

                Transaction.category_id
                == budget.category_id,

                Transaction.transaction_type
                == "expense",

                Transaction.transaction_date
                >= month_start,

                Transaction.transaction_date
                < month_end,
            )
            .scalar()
        )

        spent = float(
            spent or 0
        )

        amount = float(
            budget.amount or 0
        )

        percentage = (
            round(
                (
                    spent
                    / amount
                )
                * 100,
                1,
            )
            if amount
            else 0
        )

        total_budget += amount

        total_budget_spent += (
            spent
        )

        budget_items.append({
            "id":
                budget.id,

            "category_id":
                budget.category_id,

            "category": (
                budget.category.to_dict()
                if budget.category
                else None
            ),

            "amount":
                amount,

            "spent":
                spent,

            "remaining":
                max(
                    amount
                    - spent,
                    0,
                ),

            "percentage":
                percentage,

            "is_over_budget":
                spent > amount,
        })

    # Show budgets closest to / over
    # their limit first.

    budget_items.sort(
        key=lambda item:
            item["percentage"],
        reverse=True,
    )

    budget_percentage = (
        round(
            (
                total_budget_spent
                / total_budget
            )
            * 100,
            1,
        )
        if total_budget
        else 0
    )

    # -----------------------------------------------------
    # NOTIFICATIONS
    # -----------------------------------------------------

    unread_notifications = (
        Notification.query
        .filter_by(
            user_id=user.id,
            is_read=False,
        )
        .count()
    )

    # -----------------------------------------------------
    # RESPONSE
    # -----------------------------------------------------

    return jsonify({

        "available_balance":
            available_balance,

        "safe_to_spend":
            safe[
                "safe_to_spend"
            ],

        "income_this_month":
            income,

        "expenses_this_month":
            expenses,

        "net_cash_flow":
            net_cash_flow,

        "savings_rate":
            current_savings_rate,

        "upcoming_bills":
            upcoming_total,

        "transaction_count":
            transaction_count,

        "unread_notifications":
            unread_notifications,

        "recent_transactions": [
            transaction.to_dict()
            for transaction
            in recent_transactions
        ],

        "accounts":
            account_items,

        "upcoming_bill_items":
            bill_items,

        "goals":
            goal_items,

        "budget_summary": {
            "total_budget":
                round(
                    total_budget,
                    2,
                ),

            "spent":
                round(
                    total_budget_spent,
                    2,
                ),

            "remaining":
                round(
                    max(
                        total_budget
                        - total_budget_spent,
                        0,
                    ),
                    2,
                ),

            "percentage":
                budget_percentage,
        },

        "budgets":
            budget_items[:4],

    }), 200


# =========================================================
# ANALYTICS SUMMARY
# =========================================================

@analytics_bp.get(
    "/summary"
)
@jwt_required()
def analytics_summary():
    user = current_user()

    year, month = (
        get_period()
    )

    if not year:
        return jsonify({
            "error":
                "Invalid analytics period."
        }), 400

    income, expenses = (
        month_totals(
            user.id,
            year,
            month,
        )
    )

    previous_year, previous_month = (
        shift_month(
            year,
            month,
            -1,
        )
    )

    previous_income, previous_expenses = (
        month_totals(
            user.id,
            previous_year,
            previous_month,
        )
    )

    income = float(
        income or 0
    )

    expenses = float(
        expenses or 0
    )

    previous_income = float(
        previous_income or 0
    )

    previous_expenses = float(
        previous_expenses or 0
    )

    net_cash_flow = (
        income
        - expenses
    )

    previous_net = (
        previous_income
        - previous_expenses
    )

    return jsonify({
        "year":
            year,

        "month":
            month,

        "income":
            income,

        "expenses":
            expenses,

        "net_cash_flow":
            net_cash_flow,

        "savings_rate":
            savings_rate(
                income,
                expenses,
            ),

        "income_change":
            percent_change(
                income,
                previous_income,
            ),

        "expense_change":
            percent_change(
                expenses,
                previous_expenses,
            ),

        "net_change":
            percent_change(
                net_cash_flow,
                previous_net,
            ),

        "previous_month": {
            "year":
                previous_year,

            "month":
                previous_month,

            "income":
                previous_income,

            "expenses":
                previous_expenses,

            "net_cash_flow":
                previous_net,
        },
    }), 200


# =========================================================
# SPENDING BY CATEGORY
# =========================================================

@analytics_bp.get(
    "/spending-by-category"
)
@jwt_required()
def spending_by_category():
    user = current_user()

    year, month = (
        get_period()
    )

    if not year:
        return jsonify({
            "error":
                "Invalid analytics period."
        }), 400

    start, end = (
        month_bounds(
            year,
            month,
        )
    )

    rows = (
        db.session.query(
            Category.id,
            Category.name,

            func.coalesce(
                func.sum(
                    Transaction.amount
                ),
                0,
            ).label(
                "spent"
            ),
        )
        .join(
            Transaction,
            Transaction.category_id
            == Category.id,
        )
        .filter(
            Transaction.user_id
            == user.id,

            Transaction.transaction_type
            == "expense",

            Transaction.transaction_date
            >= start,

            Transaction.transaction_date
            < end,
        )
        .group_by(
            Category.id,
            Category.name,
        )
        .order_by(
            func.sum(
                Transaction.amount
            ).desc()
        )
        .all()
    )

    total_spent = sum(
        float(
            row.spent or 0
        )
        for row in rows
    )

    categories = []

    for row in rows:
        spent = float(
            row.spent or 0
        )

        percentage = (
            round(
                spent
                / total_spent
                * 100,
                1,
            )
            if total_spent
            else 0
        )

        categories.append({
            "category_id":
                row.id,

            "name":
                row.name,

            "spent":
                spent,

            "percentage":
                percentage,
        })

    return jsonify({
        "year":
            year,

        "month":
            month,

        "total_spent":
            total_spent,

        "categories":
            categories,
    }), 200


# =========================================================
# MONTHLY TREND
# =========================================================

@analytics_bp.get(
    "/monthly-trend"
)
@jwt_required()
def monthly_trend():
    user = current_user()

    now = datetime.utcnow()

    try:
        months = int(
            request.args.get(
                "months",
                6,
            )
        )

    except (TypeError, ValueError):
        months = 6

    months = max(
        1,
        min(
            months,
            24,
        ),
    )

    points = []

    for offset in range(
        months - 1,
        -1,
        -1,
    ):
        year, month = (
            shift_month(
                now.year,
                now.month,
                -offset,
            )
        )

        income, expenses = (
            month_totals(
                user.id,
                year,
                month,
            )
        )

        income = float(
            income or 0
        )

        expenses = float(
            expenses or 0
        )

        points.append({
            "year":
                year,

            "month":
                month,

            "income":
                income,

            "expenses":
                expenses,

            "net_cash_flow":
                income
                - expenses,

            "savings_rate":
                savings_rate(
                    income,
                    expenses,
                ),
        })

    return jsonify({
        "trend":
            points
    }), 200


# =========================================================
# ACCOUNT BREAKDOWN
# =========================================================

@analytics_bp.get(
    "/accounts"
)
@jwt_required()
def account_breakdown():
    user = current_user()

    accounts = (
        Account.query
        .filter_by(
            user_id=user.id,
            is_archived=False,
        )
        .order_by(
            Account.balance.desc()
        )
        .all()
    )

    total = sum(
        float(
            account.balance or 0
        )
        for account in accounts
    )

    rows = []

    for account in accounts:
        balance = float(
            account.balance or 0
        )

        percentage = (
            round(
                balance
                / total
                * 100,
                1,
            )
            if total > 0
            else 0
        )

        rows.append({
            "id":
                account.id,

            "name":
                account.name,

            "account_type":
                account.account_type,

            "institution":
                account.institution,

            "balance":
                balance,

            "currency":
                account.currency,

            "percentage":
                percentage,
        })

    return jsonify({
        "total_balance":
            total,

        "accounts":
            rows,
    }), 200


# =========================================================
# INSIGHTS
# =========================================================

@analytics_bp.get(
    "/insights"
)
@jwt_required()
def insights():
    user = current_user()

    year, month = (
        get_period()
    )

    if not year:
        return jsonify({
            "error":
                "Invalid analytics period."
        }), 400

    start, end = (
        month_bounds(
            year,
            month,
        )
    )

    income, expenses = (
        month_totals(
            user.id,
            year,
            month,
        )
    )

    income = float(
        income or 0
    )

    expenses = float(
        expenses or 0
    )

    transaction_count = (
        Transaction.query
        .filter(
            Transaction.user_id
            == user.id,

            Transaction.transaction_date
            >= start,

            Transaction.transaction_date
            < end,
        )
        .count()
    )

    expense_count = (
        Transaction.query
        .filter(
            Transaction.user_id
            == user.id,

            Transaction.transaction_type
            == "expense",

            Transaction.transaction_date
            >= start,

            Transaction.transaction_date
            < end,
        )
        .count()
    )

    average_expense = (
        expenses
        / expense_count
        if expense_count
        else 0
    )

    largest_expense = (
        Transaction.query
        .filter(
            Transaction.user_id
            == user.id,

            Transaction.transaction_type
            == "expense",

            Transaction.transaction_date
            >= start,

            Transaction.transaction_date
            < end,
        )
        .order_by(
            Transaction.amount.desc()
        )
        .first()
    )

    return jsonify({
        "transaction_count":
            transaction_count,

        "expense_count":
            expense_count,

        "average_expense":
            average_expense,

        "largest_expense": (
            largest_expense.to_dict()
            if largest_expense
            else None
        ),

        "savings_rate":
            savings_rate(
                income,
                expenses,
            ),
    }), 200