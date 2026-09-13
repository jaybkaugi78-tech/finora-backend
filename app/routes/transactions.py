
from datetime import datetime
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models import Account, Category, Transaction
from app.services.finance_service import apply_transaction_to_accounts
from app.utils.auth import current_user

transactions_bp = Blueprint("transactions", __name__)
VALID_TYPES = {"income", "expense", "transfer"}

def parse_date(value):
    if not value:
        return datetime.utcnow()
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)

@transactions_bp.get("")
@jwt_required()
def list_transactions():
    user = current_user()
    q = Transaction.query.filter_by(user_id=user.id)
    if request.args.get("type"):
        q = q.filter_by(transaction_type=request.args["type"])
    if request.args.get("category_id"):
        q = q.filter_by(category_id=int(request.args["category_id"]))
    if request.args.get("account_id"):
        q = q.filter_by(account_id=int(request.args["account_id"]))
    if request.args.get("search"):
        p = f"%{request.args['search']}%"
        q = q.filter(db.or_(Transaction.merchant.ilike(p), Transaction.description.ilike(p), Transaction.notes.ilike(p)))
    rows = q.order_by(Transaction.transaction_date.desc()).all()
    return jsonify({"transactions": [t.to_dict() for t in rows]}), 200

@transactions_bp.post("")
@jwt_required()
def create_transaction():
    user = current_user()
    data = request.get_json() or {}
    kind = (data.get("transaction_type") or "").lower()
    if kind not in VALID_TYPES:
        return jsonify({"error": "Invalid transaction type."}), 400
    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return jsonify({"error": "Amount must be a valid number."}), 400
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than zero."}), 400

    source = Account.query.filter_by(id=data.get("account_id"), user_id=user.id).first()
    if not source:
        return jsonify({"error": "Account not found."}), 404

    category_id = data.get("category_id")
    destination_id = data.get("destination_account_id")

    if kind == "transfer":
        destination = Account.query.filter_by(id=destination_id, user_id=user.id).first()
        if not destination:
            return jsonify({"error": "Destination account not found."}), 404
        if destination.id == source.id:
            return jsonify({"error": "Transfer accounts must be different."}), 400
        category_id = None
    else:
        category = Category.query.filter_by(id=category_id, user_id=user.id).first()
        if not category:
            return jsonify({"error": "Category not found."}), 404

    tx = Transaction(
        user_id=user.id, transaction_type=kind, amount=amount, account_id=source.id,
        destination_account_id=destination_id if kind == "transfer" else None,
        category_id=category_id, merchant=data.get("merchant"), description=data.get("description"),
        notes=data.get("notes"), transaction_date=parse_date(data.get("transaction_date")),
        is_recurring=bool(data.get("is_recurring", False)),
    )
    db.session.add(tx)
    db.session.flush()
    try:
        apply_transaction_to_accounts(tx)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({"transaction": tx.to_dict()}), 201

@transactions_bp.get("/<int:transaction_id>")
@jwt_required()
def get_transaction(transaction_id):
    user = current_user()
    tx = Transaction.query.filter_by(id=transaction_id, user_id=user.id).first_or_404()
    return jsonify({"transaction": tx.to_dict()}), 200

@transactions_bp.patch("/<int:transaction_id>")
@jwt_required()
def update_transaction(transaction_id):
    user = current_user()
    tx = Transaction.query.filter_by(id=transaction_id, user_id=user.id).first_or_404()
    data = request.get_json() or {}
    try:
        apply_transaction_to_accounts(tx, reverse=True)
        if "amount" in data:
            amount = float(data["amount"])
            if amount <= 0:
                raise ValueError("Amount must be greater than zero.")
            tx.amount = amount
        if "merchant" in data: tx.merchant = data["merchant"]
        if "description" in data: tx.description = data["description"]
        if "notes" in data: tx.notes = data["notes"]
        if "transaction_date" in data: tx.transaction_date = parse_date(data["transaction_date"])
        if "category_id" in data and tx.transaction_type != "transfer":
            category = Category.query.filter_by(id=data["category_id"], user_id=user.id).first()
            if not category: raise ValueError("Category not found.")
            tx.category_id = category.id
        apply_transaction_to_accounts(tx)
        db.session.commit()
    except (ValueError, TypeError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({"transaction": tx.to_dict()}), 200

@transactions_bp.delete("/<int:transaction_id>")
@jwt_required()
def delete_transaction(transaction_id):
    user = current_user()
    tx = Transaction.query.filter_by(id=transaction_id, user_id=user.id).first_or_404()
    try:
        apply_transaction_to_accounts(tx, reverse=True)
        db.session.delete(tx)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    return jsonify({"message": "Transaction deleted."}), 200
