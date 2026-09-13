
from datetime import date
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
from app.extensions import db
from app.models import Goal, GoalContribution
from app.utils.auth import current_user

goals_bp = Blueprint("goals", __name__)

@goals_bp.get("")
@jwt_required()
def list_goals():
    user = current_user()
    rows = Goal.query.filter_by(user_id=user.id).order_by(Goal.created_at.desc()).all()
    return jsonify({"goals": [g.to_dict() for g in rows]}), 200

@goals_bp.post("")
@jwt_required()
def create_goal():
    user = current_user()
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    try: target = float(data.get("target_amount"))
    except (TypeError, ValueError): return jsonify({"error": "Target amount must be valid."}), 400
    if not name or target <= 0: return jsonify({"error": "Name and positive target amount are required."}), 400
    target_date = date.fromisoformat(data["target_date"]) if data.get("target_date") else None
    goal = Goal(user_id=user.id, name=name, target_amount=target, target_date=target_date, notes=data.get("notes"))
    db.session.add(goal); db.session.commit()
    return jsonify({"goal": goal.to_dict()}), 201

@goals_bp.post("/<int:goal_id>/contributions")
@jwt_required()
def add_contribution(goal_id):
    user = current_user()
    goal = Goal.query.filter_by(id=goal_id, user_id=user.id).first_or_404()
    data = request.get_json() or {}
    try: amount = float(data.get("amount"))
    except (TypeError, ValueError): return jsonify({"error": "Contribution amount must be valid."}), 400
    if amount <= 0: return jsonify({"error": "Contribution amount must be greater than zero."}), 400
    c = GoalContribution(goal_id=goal.id, amount=amount, note=data.get("note"))
    db.session.add(c); db.session.flush()
    if goal.current_amount() >= float(goal.target_amount): goal.is_completed = True
    db.session.commit()
    return jsonify({"contribution": c.to_dict(), "goal": goal.to_dict()}), 201

@goals_bp.patch("/<int:goal_id>")
@jwt_required()
def update_goal(goal_id):
    user = current_user()
    goal = Goal.query.filter_by(id=goal_id, user_id=user.id).first_or_404()
    data = request.get_json() or {}
    if "name" in data: goal.name = data["name"]
    if "target_amount" in data: goal.target_amount = float(data["target_amount"])
    if "target_date" in data: goal.target_date = date.fromisoformat(data["target_date"]) if data["target_date"] else None
    if "notes" in data: goal.notes = data["notes"]
    db.session.commit()
    return jsonify({"goal": goal.to_dict()}), 200

@goals_bp.delete("/<int:goal_id>")
@jwt_required()
def delete_goal(goal_id):
    user = current_user()
    goal = Goal.query.filter_by(id=goal_id, user_id=user.id).first_or_404()
    db.session.delete(goal); db.session.commit()
    return jsonify({"message": "Goal deleted."}), 200
