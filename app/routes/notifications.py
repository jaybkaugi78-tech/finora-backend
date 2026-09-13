
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models import Notification
from app.utils.auth import current_user

notifications_bp = Blueprint("notifications", __name__)

@notifications_bp.get("")
@jwt_required()
def list_notifications():
    user = current_user()
    rows = Notification.query.filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(50).all()
    return jsonify({"notifications": [n.to_dict() for n in rows]}), 200

@notifications_bp.patch("/<int:notification_id>/read")
@jwt_required()
def mark_read(notification_id):
    user = current_user()
    n = Notification.query.filter_by(id=notification_id, user_id=user.id).first_or_404()
    n.is_read = True; db.session.commit()
    return jsonify({"notification": n.to_dict()}), 200
