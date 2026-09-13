
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models import Category
from app.utils.auth import current_user

categories_bp = Blueprint("categories", __name__)

@categories_bp.get("")
@jwt_required()
def list_categories():
    user = current_user()
    q = Category.query.filter_by(user_id=user.id)
    category_type = request.args.get("type")
    if category_type:
        q = q.filter_by(category_type=category_type)
    rows = q.order_by(Category.name.asc()).all()
    return jsonify({"categories": [c.to_dict() for c in rows]}), 200

@categories_bp.post("")
@jwt_required()
def create_category():
    user = current_user()
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    category_type = (data.get("category_type") or "").strip().lower()
    if not name or category_type not in {"income", "expense"}:
        return jsonify({"error": "Valid name and category_type are required."}), 400
    if Category.query.filter_by(user_id=user.id, name=name, category_type=category_type).first():
        return jsonify({"error": "Category already exists."}), 409
    category = Category(user_id=user.id, name=name, category_type=category_type, icon=data.get("icon"), is_default=False)
    db.session.add(category)
    db.session.commit()
    return jsonify({"category": category.to_dict()}), 201
