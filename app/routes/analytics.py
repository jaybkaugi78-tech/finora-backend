
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from app.extensions import db
from app.models import Category, Transaction
from app.services.finance_service import account_total, month_bounds, month_totals, safe_to_spend, upcoming_bills_total
from app.utils.auth import current_user

analytics_bp = Blueprint("analytics", __name__)

@analytics_bp.get("/dashboard")
@jwt_required()
def dashboard():
    user = current_user(); now = datetime.utcnow()
    income, expenses = month_totals(user.id, now.year, now.month)
    safe = safe_to_spend(user.id)
    recent = Transaction.query.filter_by(user_id=user.id).order_by(Transaction.transaction_date.desc()).limit(5).all()
    return jsonify({
        "available_balance": account_total(user.id),
        "income_this_month": income,
        "expenses_this_month": expenses,
        "upcoming_bills": upcoming_bills_total(user.id, 30),
        "safe_to_spend": safe["safe_to_spend"],
        "recent_transactions": [t.to_dict() for t in recent],
    }), 200

@analytics_bp.get("/spending-by-category")
@jwt_required()
def spending_by_category():
    user = current_user(); now = datetime.utcnow()
    year = int(request.args.get("year", now.year)); month = int(request.args.get("month", now.month))
    start, end = month_bounds(year, month)
    rows = db.session.query(
        Category.id, Category.name, func.coalesce(func.sum(Transaction.amount), 0).label("spent")
    ).join(Transaction, Transaction.category_id == Category.id).filter(
        Transaction.user_id == user.id,
        Transaction.transaction_type == "expense",
        Transaction.transaction_date >= start,
        Transaction.transaction_date < end,
    ).group_by(Category.id, Category.name).order_by(func.sum(Transaction.amount).desc()).all()
    return jsonify({"categories": [{"category_id": r.id, "name": r.name, "spent": float(r.spent or 0)} for r in rows]}), 200

@analytics_bp.get("/monthly-trend")
@jwt_required()
def monthly_trend():
    user = current_user(); now = datetime.utcnow(); points = []
    for offset in range(5, -1, -1):
        m, y = now.month - offset, now.year
        while m <= 0: m += 12; y -= 1
        income, expenses = month_totals(user.id, y, m)
        points.append({"year": y, "month": m, "income": income, "expenses": expenses})
    return jsonify({"trend": points}), 200
