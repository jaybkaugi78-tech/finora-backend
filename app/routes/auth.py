
from flask import Blueprint, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from sqlalchemy.exc import IntegrityError

from ..extensions import db, limiter
from ..models import User
from .common import body, fail
from app.services.category_service import create_default_categories


bp = Blueprint("auth", __name__)


def auth_response(user, status=200):
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify(
        access_token=access_token,
        token=access_token,
        refresh_token=refresh_token,
        user=user.to_dict(),
    ), status


@bp.post("/auth/register")
@limiter.limit("5 per minute")
def register():
    data = body()

    name = str(
        data.get("full_name") or data.get("name") or ""
    ).strip()

    email = str(
        data.get("email") or ""
    ).strip().lower()

    password = data.get("password") or ""

    if (
        not name
        or "@" not in email
        or not isinstance(password, str)
        or len(password) < 10
    ):
        return fail(
            "Name, valid email and password of at least "
            "10 characters required."
        )

    if User.query.filter_by(email=email).first():
        return fail("Email already registered.", 409)

    try:
        user = User(
            full_name=name,
            email=email,
        )

        user.set_password(password)

        db.session.add(user)

        # Assign the user's ID without committing.
        db.session.flush()

        # Create their default income and expense categories.
        create_default_categories(user.id)

        # Commit both the user and categories together.
        db.session.commit()

    except IntegrityError:
        db.session.rollback()
        return fail("Email already registered.", 409)

    except Exception:
        db.session.rollback()
        raise

    return auth_response(user, 201)


@bp.post("/auth/login")
@limiter.limit("10 per minute")
def login():
    data = body()

    email = str(
        data.get("email") or ""
    ).strip().lower()

    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return fail("Invalid credentials.", 401)

    return auth_response(user)


@bp.post("/auth/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()

    access_token = create_access_token(identity=identity)

    return jsonify(
        access_token=access_token,
        token=access_token,
    )


@bp.get("/auth/me")
@jwt_required()
def me():
    user_id = int(get_jwt_identity())

    user = db.session.get(User, user_id)

    if not user:
        return fail("User not found.", 404)

    return jsonify(user=user.to_dict())
