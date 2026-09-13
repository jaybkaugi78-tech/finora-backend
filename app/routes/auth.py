
from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token
from app.extensions import db
from app.models import Account, User
from app.services.category_service import create_default_categories

auth_bp = Blueprint("auth", __name__)

@auth_bp.post("/register")
def register():
    data = request.get_json() or {}
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not full_name or not email or not password:
        return jsonify({"error": "Full name, email and password are required."}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with that email already exists."}), 409

    user = User(full_name=full_name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    db.session.add(Account(
        user_id=user.id, name="M-Pesa", account_type="mobile_money",
        currency="KES", balance=0, is_default=True
    ))
    create_default_categories(user.id)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"access_token": token, "user": user.to_dict()}), 201

@auth_bp.post("/login")
def login():
    data = request.get_json() or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password."}), 401
    if not user.is_active:
        return jsonify({"error": "This account is disabled."}), 403
    return jsonify({"access_token": create_access_token(identity=str(user.id)), "user": user.to_dict()}), 200
