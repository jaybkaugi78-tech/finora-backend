from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from app.extensions import db
from app.models import Budget, Category, Transaction
from app.services.finance_service import month_bounds
from app.utils.auth import current_user


budgets_bp = Blueprint(
    "budgets",
    __name__,
)


def validate_period(month, year):
    try:
        month = int(month)
        year = int(year)
    except (TypeError, ValueError):
        raise ValueError(
            "Month and year must be valid numbers."
        )

    if not 1 <= month <= 12:
        raise ValueError(
            "Month must be between 1 and 12."
        )

    if year < 2000 or year > 2100:
        raise ValueError(
            "Enter a valid year."
        )

    return month, year


def spent_for_budget(
    user_id,
    budget,
):
    start, end = month_bounds(
        budget.year,
        budget.month,
    )

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
            == user_id,

            Transaction.category_id
            == budget.category_id,

            Transaction.transaction_type
            == "expense",

            Transaction.transaction_date
            >= start,

            Transaction.transaction_date
            < end,
        )
        .scalar()
    )

    return float(
        spent or 0
    )


def serialize_budget(
    user_id,
    budget,
):
    spent = spent_for_budget(
        user_id,
        budget,
    )

    data = budget.to_dict(
        spent
    )

    amount = float(
        budget.amount or 0
    )

    data["over_by"] = max(
        spent - amount,
        0,
    )

    data["is_over_budget"] = (
        spent > amount
    )

    return data


@budgets_bp.get("")
@jwt_required()
def list_budgets():
    user = current_user()
    now = datetime.utcnow()

    try:
        month, year = (
            validate_period(
                request.args.get(
                    "month",
                    now.month,
                ),
                request.args.get(
                    "year",
                    now.year,
                ),
            )
        )
    except ValueError as exc:
        return jsonify({
            "error": str(exc)
        }), 400

    budgets = (
        Budget.query
        .filter_by(
            user_id=user.id,
            month=month,
            year=year,
        )
        .order_by(
            Budget.created_at.asc()
        )
        .all()
    )

    serialized = [
        serialize_budget(
            user.id,
            budget,
        )
        for budget in budgets
    ]

    total_budget = sum(
        item["amount"]
        for item in serialized
    )

    total_spent = sum(
        item["spent"]
        for item in serialized
    )

    total_remaining = max(
        total_budget -
        total_spent,
        0,
    )

    total_over = max(
        total_spent -
        total_budget,
        0,
    )

    percentage = (
        round(
            total_spent /
            total_budget *
            100,
            1,
        )
        if total_budget
        else 0
    )

    return jsonify({
        "budgets": serialized,

        "summary": {
            "total_budget":
                total_budget,

            "total_spent":
                total_spent,

            "total_remaining":
                total_remaining,

            "total_over":
                total_over,

            "percentage":
                percentage,
        },

        "month": month,
        "year": year,
    }), 200


@budgets_bp.post("")
@jwt_required()
def create_budget():
    user = current_user()
    data = request.get_json() or {}

    category = (
        Category.query.filter_by(
            id=data.get(
                "category_id"
            ),
            user_id=user.id,
            category_type="expense",
        ).first()
    )

    if not category:
        return jsonify({
            "error":
                "Expense category not found."
        }), 404

    try:
        amount = float(
            data.get("amount")
        )

        month, year = (
            validate_period(
                data.get("month"),
                data.get("year"),
            )
        )

    except (TypeError, ValueError) as exc:
        return jsonify({
            "error":
                str(exc)
                if str(exc)
                else "Invalid budget values."
        }), 400

    if amount <= 0:
        return jsonify({
            "error":
                "Budget amount must be greater than zero."
        }), 400

    existing = (
        Budget.query.filter_by(
            user_id=user.id,
            category_id=category.id,
            month=month,
            year=year,
        ).first()
    )

    if existing:
        return jsonify({
            "error":
                "A budget already exists for this category and month."
        }), 409

    budget = Budget(
        user_id=user.id,
        category_id=category.id,
        amount=amount,
        month=month,
        year=year,
    )

    db.session.add(budget)
    db.session.commit()

    return jsonify({
        "budget":
            serialize_budget(
                user.id,
                budget,
            )
    }), 201


@budgets_bp.patch(
    "/<int:budget_id>"
)
@jwt_required()
def update_budget(budget_id):
    user = current_user()

    budget = (
        Budget.query.filter_by(
            id=budget_id,
            user_id=user.id,
        ).first_or_404()
    )

    data = request.get_json() or {}

    if "amount" in data:
        try:
            amount = float(
                data["amount"]
            )
        except (
            TypeError,
            ValueError,
        ):
            return jsonify({
                "error":
                    "Budget amount must be a valid number."
            }), 400

        if amount <= 0:
            return jsonify({
                "error":
                    "Budget amount must be greater than zero."
            }), 400

        budget.amount = amount

    db.session.commit()

    return jsonify({
        "budget":
            serialize_budget(
                user.id,
                budget,
            )
    }), 200


@budgets_bp.delete(
    "/<int:budget_id>"
)
@jwt_required()
def delete_budget(budget_id):
    user = current_user()

    budget = (
        Budget.query.filter_by(
            id=budget_id,
            user_id=user.id,
        ).first_or_404()
    )

    db.session.delete(
        budget
    )

    db.session.commit()

    return jsonify({
        "message":
            "Budget deleted."
    }), 200