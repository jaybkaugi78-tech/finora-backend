from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import User
from app.utils.auth import current_user


users_bp = Blueprint("users", __name__)


VALID_CURRENCIES = {
    "KES",
    "USD",
    "GBP",
    "EUR",
}

VALID_TIMEZONES = {
    "Africa/Nairobi",
    "UTC",
    "Europe/London",
    "America/New_York",
    "Asia/Dubai",
}


def clean_text(value):
    if value is None:
        return ""

    return str(value).strip()


@users_bp.get("/me")
@jwt_required()
def get_me():
    user = current_user()

    return jsonify({
        "user": user.to_dict()
    }), 200


@users_bp.patch("/me")
@jwt_required()
def update_me():
    user = current_user()

    data = request.get_json() or {}

    if "full_name" in data:
        full_name = clean_text(
            data.get("full_name")
        )

        if not full_name:
            return jsonify({
                "error":
                    "Full name is required."
            }), 400

        if len(full_name) > 120:
            return jsonify({
                "error":
                    "Full name is too long."
            }), 400

        user.full_name = full_name


    if "email" in data:
        email = (
            clean_text(
                data.get("email")
            )
            .lower()
        )

        if not email:
            return jsonify({
                "error":
                    "Email is required."
            }), 400

        if (
            "@" not in email
            or "." not in email
        ):
            return jsonify({
                "error":
                    "Enter a valid email address."
            }), 400

        existing_user = (
            User.query
            .filter(
                User.email == email,
                User.id != user.id,
            )
            .first()
        )

        if existing_user:
            return jsonify({
                "error":
                    "That email is already in use."
            }), 409

        user.email = email


    if "currency" in data:
        currency = (
            clean_text(
                data.get("currency")
            )
            .upper()
        )

        if currency not in VALID_CURRENCIES:
            return jsonify({
                "error":
                    "Unsupported currency."
            }), 400

        user.currency = currency


    if "country" in data:
        country = clean_text(
            data.get("country")
        )

        if not country:
            return jsonify({
                "error":
                    "Country is required."
            }), 400

        if len(country) > 80:
            return jsonify({
                "error":
                    "Country name is too long."
            }), 400

        user.country = country


    if "timezone" in data:
        timezone = clean_text(
            data.get("timezone")
        )

        if timezone not in VALID_TIMEZONES:
            return jsonify({
                "error":
                    "Unsupported timezone."
            }), 400

        user.timezone = timezone


    db.session.commit()

    return jsonify({
        "message":
            "Settings updated successfully.",

        "user":
            user.to_dict(),
    }), 200


@users_bp.patch("/me/password")
@jwt_required()
def change_password():
    user = current_user()

    data = request.get_json() or {}

    current_password = str(
        data.get(
            "current_password",
            ""
        )
    )

    new_password = str(
        data.get(
            "new_password",
            ""
        )
    )

    confirm_password = str(
        data.get(
            "confirm_password",
            ""
        )
    )


    if not current_password:
        return jsonify({
            "error":
                "Current password is required."
        }), 400


    if not user.check_password(
        current_password
    ):
        return jsonify({
            "error":
                "Current password is incorrect."
        }), 400


    if len(new_password) < 8:
        return jsonify({
            "error":
                "New password must be at least 8 characters."
        }), 400


    if (
        new_password
        != confirm_password
    ):
        return jsonify({
            "error":
                "New passwords do not match."
        }), 400


    if user.check_password(
        new_password
    ):
        return jsonify({
            "error":
                "New password must be different from your current password."
        }), 400


    user.set_password(
        new_password
    )

    db.session.commit()

    return jsonify({
        "message":
            "Password changed successfully."
    }), 200