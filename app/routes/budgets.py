
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from app.extensions import db
from app.models import Budget, Category, Transaction
from app.utils.auth import current_user
from app.services.finance_service import month_bounds

budgets_bp = Blueprint("budgets", __name__)

def spent_for_budget(user_id, budget):
    start, end = month_bounds(budget.year, budget.month)
    spent = db.session.query(func.coalesce(func.sum(Transaction.amount), 0)).filter(
        Transaction.user_id == user_id,
        Transaction.category_id == budget.category_id,
        Transaction.transaction_type == "expense",
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end,
    ).scalar()
    return float(spent or 0)

@budgets_bp.get("")
@jwt_required()
def list_budgets():
    user = current_user()
    now = datetime.utcnow()
    month = int(request.args.get("month", now.month))
    year = int(request.args.get("year", now.year))
    rows = Budget.query.filter_by(user_id=user.id, month=month, year=year).all()
    return jsonify({"budgets": [b.to_dict(spent_for_budget(user.id, b)) for b in rows]}), 200

@budgets_bp.post("")
@jwt_required()
def create_budget():
    user = current_user()
    data = request.get_json() or {}
    category = Category.query.filter_by(id=data.get("category_id"), user_id=user.id, category_type="expense").first()
    if not category:
        return jsonify({"error": "Expense category not found."}), 404
    try:
        amount = float(data.get("amount")); month = int(data.get("month")); year = int(data.get("year"))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid budget values."}), 400
    if amount <= 0 or not 1 <= month <= 12:
        return jsonify({"error": "Invalid budget values."}), 400
    if Budget.query.filter_by(user_id=user.id, category_id=category.id, month=month, year=year).first():
        return jsonify({"error": "Budget already exists for this category and month."}), 409
    budget = Budget(user_id=user.id, category_id=category.id, amount=amount, month=month, year=year)
    db.session.add(budget); db.session.commit()
    return jsonify({"budget": budget.to_dict(0)}), 201

@budgets_bp.patch("/<int:budget_id>")
@jwt_required()
def update_budget(budget_id):
    user = current_user()
    budget = Budget.query.filter_by(id=budget_id, user_id=user.id).first_or_404()
    data = request.get_json() or {}
    if "amount" in data:
        amount = float(data["amount"])
        if amount <= 0: return jsonify({"error": "Amount must be greater than zero."}), 400
        budget.amount = amount
    db.session.commit()
    return jsonify({"budget": budget.to_dict(spent_for_budget(user.id, budget))}), 200

@budgets_bp.delete("/<int:budget_id>")
@jwt_required()
def delete_budget(budget_id):
    user = current_user()
    budget = Budget.query.filter_by(id=budget_id, user_id=user.id).first_or_404()
    db.session.delete(budget); db.session.commit()
    return jsonify({"message": "Budget deleted."}), 200
