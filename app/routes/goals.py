from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Goal, GoalContribution
from app.utils.auth import current_user


goals_bp = Blueprint(
    "goals",
    __name__,
)


def parse_target_amount(value):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            "Target amount must be valid."
        )

    if amount <= 0:
        raise ValueError(
            "Target amount must be greater than zero."
        )

    return amount


def parse_target_date(value):
    if not value:
        return None

    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(
            "Target date must be a valid date."
        )


def sync_goal_completion(goal):
    goal.is_completed = (
        goal.current_amount()
        >= float(goal.target_amount)
    )


def serialize_goal(goal):
    data = goal.to_dict()

    contributions = sorted(
        goal.contributions,
        key=lambda item:
            item.contributed_at,
        reverse=True,
    )

    data["contributions"] = [
        contribution.to_dict()
        for contribution
        in contributions
    ]

    data["contribution_count"] = (
        len(contributions)
    )

    return data


@goals_bp.get("")
@jwt_required()
def list_goals():
    user = current_user()

    goals = (
        Goal.query
        .filter_by(
            user_id=user.id
        )
        .order_by(
            Goal.created_at.desc()
        )
        .all()
    )

    return jsonify({
        "goals": [
            serialize_goal(goal)
            for goal in goals
        ]
    }), 200


@goals_bp.get("/<int:goal_id>")
@jwt_required()
def get_goal(goal_id):
    user = current_user()

    goal = (
        Goal.query
        .filter_by(
            id=goal_id,
            user_id=user.id,
        )
        .first_or_404()
    )

    return jsonify({
        "goal":
            serialize_goal(goal)
    }), 200


@goals_bp.post("")
@jwt_required()
def create_goal():
    user = current_user()
    data = request.get_json() or {}

    name = (
        data.get("name")
        or ""
    ).strip()

    if not name:
        return jsonify({
            "error":
                "Goal name is required."
        }), 400

    try:
        target_amount = (
            parse_target_amount(
                data.get(
                    "target_amount"
                )
            )
        )

        target_date = (
            parse_target_date(
                data.get(
                    "target_date"
                )
            )
        )

    except ValueError as exc:
        return jsonify({
            "error": str(exc)
        }), 400

    notes = (
        data.get("notes")
        or ""
    ).strip()

    goal = Goal(
        user_id=user.id,
        name=name,
        target_amount=target_amount,
        target_date=target_date,
        notes=notes or None,
        is_completed=False,
    )

    db.session.add(goal)
    db.session.commit()

    return jsonify({
        "goal":
            serialize_goal(goal)
    }), 201


@goals_bp.patch(
    "/<int:goal_id>"
)
@jwt_required()
def update_goal(goal_id):
    user = current_user()

    goal = (
        Goal.query
        .filter_by(
            id=goal_id,
            user_id=user.id,
        )
        .first_or_404()
    )

    data = request.get_json() or {}

    if "name" in data:
        name = (
            data.get("name")
            or ""
        ).strip()

        if not name:
            return jsonify({
                "error":
                    "Goal name is required."
            }), 400

        goal.name = name

    if "target_amount" in data:
        try:
            goal.target_amount = (
                parse_target_amount(
                    data.get(
                        "target_amount"
                    )
                )
            )
        except ValueError as exc:
            return jsonify({
                "error": str(exc)
            }), 400

    if "target_date" in data:
        try:
            goal.target_date = (
                parse_target_date(
                    data.get(
                        "target_date"
                    )
                )
            )
        except ValueError as exc:
            return jsonify({
                "error": str(exc)
            }), 400

    if "notes" in data:
        notes = (
            data.get("notes")
            or ""
        ).strip()

        goal.notes = (
            notes or None
        )

    sync_goal_completion(goal)

    db.session.commit()

    return jsonify({
        "goal":
            serialize_goal(goal)
    }), 200


@goals_bp.delete(
    "/<int:goal_id>"
)
@jwt_required()
def delete_goal(goal_id):
    user = current_user()

    goal = (
        Goal.query
        .filter_by(
            id=goal_id,
            user_id=user.id,
        )
        .first_or_404()
    )

    db.session.delete(goal)
    db.session.commit()

    return jsonify({
        "message":
            "Goal deleted."
    }), 200


@goals_bp.post(
    "/<int:goal_id>/contributions"
)
@jwt_required()
def add_contribution(goal_id):
    user = current_user()

    goal = (
        Goal.query
        .filter_by(
            id=goal_id,
            user_id=user.id,
        )
        .first_or_404()
    )

    data = request.get_json() or {}

    try:
        amount = float(
            data.get("amount")
        )
    except (TypeError, ValueError):
        return jsonify({
            "error":
                "Contribution amount must be valid."
        }), 400

    if amount <= 0:
        return jsonify({
            "error":
                "Contribution amount must be greater than zero."
        }), 400

    note = (
        data.get("note")
        or ""
    ).strip()

    contribution = GoalContribution(
        goal_id=goal.id,
        amount=amount,
        note=note or None,
    )

    db.session.add(
        contribution
    )

    db.session.flush()

    sync_goal_completion(goal)

    db.session.commit()

    return jsonify({
        "contribution":
            contribution.to_dict(),

        "goal":
            serialize_goal(goal),
    }), 201


@goals_bp.delete(
    "/<int:goal_id>/contributions/<int:contribution_id>"
)
@jwt_required()
def delete_contribution(
    goal_id,
    contribution_id,
):
    user = current_user()

    goal = (
        Goal.query
        .filter_by(
            id=goal_id,
            user_id=user.id,
        )
        .first_or_404()
    )

    contribution = (
        GoalContribution.query
        .filter_by(
            id=contribution_id,
            goal_id=goal.id,
        )
        .first_or_404()
    )

    db.session.delete(
        contribution
    )

    db.session.flush()

    sync_goal_completion(goal)

    db.session.commit()

    return jsonify({
        "message":
            "Contribution deleted.",

        "goal":
            serialize_goal(goal),
    }), 200