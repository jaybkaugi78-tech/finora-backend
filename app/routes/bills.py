
from datetime import date
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models import Bill
from app.utils.auth import current_user

bills_bp = Blueprint("bills", __name__)

@bills_bp.get("")
@jwt_required()
def list_bills():
    user = current_user()
    rows = Bill.query.filter_by(user_id=user.id).order_by(Bill.next_due_date.asc()).all()
    return jsonify({"bills": [b.to_dict() for b in rows]}), 200

@bills_bp.post("")
@jwt_required()
def create_bill():
    user = current_user()
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    try:
        amount = float(data.get("amount")); due = date.fromisoformat(data.get("next_due_date"))
    except (TypeError, ValueError):
        return jsonify({"error": "Amount and due date must be valid."}), 400
    if not name or amount <= 0: return jsonify({"error": "Name and positive amount are required."}), 400
    bill = Bill(
        user_id=user.id, name=name, amount=amount, category_id=data.get("category_id"),
        account_id=data.get("account_id"), frequency=data.get("frequency", "monthly"),
        next_due_date=due, reminder_days=int(data.get("reminder_days", 3)),
        is_subscription=bool(data.get("is_subscription", False)), is_active=True
    )
    db.session.add(bill); db.session.commit()
    return jsonify({"bill": bill.to_dict()}), 201

@bills_bp.patch("/<int:bill_id>")
@jwt_required()
def update_bill(bill_id):
    user = current_user()
    bill = Bill.query.filter_by(id=bill_id, user_id=user.id).first_or_404()
    data = request.get_json() or {}
    for field in ["name", "frequency", "reminder_days", "is_subscription", "is_active", "category_id", "account_id"]:
        if field in data: setattr(bill, field, data[field])
    if "amount" in data: bill.amount = float(data["amount"])
    if "next_due_date" in data: bill.next_due_date = date.fromisoformat(data["next_due_date"])
    db.session.commit()
    return jsonify({"bill": bill.to_dict()}), 200

@bills_bp.delete("/<int:bill_id>")
@jwt_required()
def delete_bill(bill_id):
    user = current_user()
    bill = Bill.query.filter_by(id=bill_id, user_id=user.id).first_or_404()
    db.session.delete(bill); db.session.commit()
    return jsonify({"message": "Bill deleted."}), 200
