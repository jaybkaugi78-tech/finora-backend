
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.utils.auth import current_user

users_bp = Blueprint("users", __name__)

@users_bp.get("/me")
@jwt_required()
def get_me():
    return jsonify({"user": current_user().to_dict()}), 200

@users_bp.patch("/me")
@jwt_required()
def update_me():
    user = current_user()
    data = request.get_json() or {}
    for field in ["full_name", "currency", "country", "timezone"]:
        if field in data and data[field] is not None:
            setattr(user, field, data[field])
    db.session.commit()
    return jsonify({"user": user.to_dict()}), 200
