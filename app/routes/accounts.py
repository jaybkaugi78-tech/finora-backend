
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models import Account
from app.utils.auth import current_user

accounts_bp = Blueprint("accounts", __name__)

@accounts_bp.get("")
@jwt_required()
def list_accounts():
    user = current_user()
    rows = Account.query.filter_by(user_id=user.id).order_by(Account.created_at.asc()).all()
    return jsonify({"accounts": [a.to_dict() for a in rows]}), 200

@accounts_bp.post("")
@jwt_required()
def create_account():
    user = current_user()
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    account_type = (data.get("account_type") or "").strip()
    if not name or not account_type:
        return jsonify({"error": "Name and account type are required."}), 400

    account = Account(
        user_id=user.id, name=name, account_type=account_type,
        institution=data.get("institution"), balance=data.get("balance", 0),
        currency=data.get("currency", user.currency), is_default=bool(data.get("is_default", False)),
    )
    if account.is_default:
        Account.query.filter_by(user_id=user.id, is_default=True).update({"is_default": False})
    db.session.add(account)
    db.session.commit()
    return jsonify({"account": account.to_dict()}), 201

@accounts_bp.patch("/<int:account_id>")
@jwt_required()
def update_account(account_id):
    user = current_user()
    account = Account.query.filter_by(id=account_id, user_id=user.id).first_or_404()
    data = request.get_json() or {}
    for field in ["name", "account_type", "institution", "currency", "is_archived"]:
        if field in data:
            setattr(account, field, data[field])
    if data.get("is_default") is True:
        Account.query.filter_by(user_id=user.id, is_default=True).update({"is_default": False})
        account.is_default = True
    db.session.commit()
    return jsonify({"account": account.to_dict()}), 200

@accounts_bp.delete("/<int:account_id>")
@jwt_required()
def delete_account(account_id):
    user = current_user()
    account = Account.query.filter_by(id=account_id, user_id=user.id).first_or_404()
    account.is_archived = True
    db.session.commit()
    return jsonify({"message": "Account archived."}), 200
