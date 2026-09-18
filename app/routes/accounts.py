from decimal import Decimal, InvalidOperation

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Account
from app.utils.auth import current_user


accounts_bp = Blueprint(
    "accounts",
    __name__,
)


VALID_ACCOUNT_TYPES = {
    "mobile_money",
    "bank",
    "cash",
    "savings",
}


VALID_CURRENCIES = {
    "KES",
    "USD",
    "EUR",
    "GBP",
}


def clean_optional_text(value):
    if value is None:
        return None

    value = str(value).strip()

    return value or None


def make_default_account(
    user_id,
    account,
):
    Account.query.filter(
        Account.user_id == user_id,
        Account.id != account.id,
    ).update(
        {
            "is_default": False
        },
        synchronize_session=False,
    )

    account.is_default = True
    account.is_archived = False


def ensure_default_account(user_id):
    default_account = (
        Account.query.filter_by(
            user_id=user_id,
            is_default=True,
            is_archived=False,
        ).first()
    )

    if default_account:
        return

    first_active = (
        Account.query.filter_by(
            user_id=user_id,
            is_archived=False,
        )
        .order_by(
            Account.created_at.asc()
        )
        .first()
    )

    if first_active:
        first_active.is_default = True


@accounts_bp.get("")
@jwt_required()
def list_accounts():
    user = current_user()

    include_archived = (
        request.args.get(
            "include_archived",
            "true",
        ).lower()
        == "true"
    )

    query = Account.query.filter_by(
        user_id=user.id
    )

    if not include_archived:
        query = query.filter_by(
            is_archived=False
        )

    rows = (
        query
        .order_by(
            Account.is_archived.asc(),
            Account.is_default.desc(),
            Account.created_at.asc(),
        )
        .all()
    )

    return jsonify({
        "accounts": [
            account.to_dict()
            for account in rows
        ]
    }), 200


@accounts_bp.post("")
@jwt_required()
def create_account():
    user = current_user()
    data = request.get_json() or {}

    name = (
        data.get("name") or ""
    ).strip()

    account_type = (
        data.get("account_type") or ""
    ).strip().lower()

    institution = clean_optional_text(
        data.get("institution")
    )

    currency = (
        data.get("currency")
        or user.currency
        or "KES"
    ).strip().upper()

    if not name:
        return jsonify({
            "error":
                "Account name is required."
        }), 400

    if account_type not in VALID_ACCOUNT_TYPES:
        return jsonify({
            "error":
                "Invalid account type."
        }), 400

    if currency not in VALID_CURRENCIES:
        return jsonify({
            "error":
                "Unsupported currency."
        }), 400

    try:
        balance = Decimal(
            str(
                data.get(
                    "balance",
                    0,
                )
            )
        )
    except (
        InvalidOperation,
        TypeError,
        ValueError,
    ):
        return jsonify({
            "error":
                "Opening balance must be a valid number."
        }), 400

    duplicate = (
        Account.query.filter(
            Account.user_id == user.id,
            db.func.lower(Account.name)
            == name.lower(),
            Account.is_archived.is_(False),
        ).first()
    )

    if duplicate:
        return jsonify({
            "error":
                "You already have an active account with this name."
        }), 409

    has_active_account = (
        Account.query.filter_by(
            user_id=user.id,
            is_archived=False,
        ).first()
        is not None
    )

    requested_default = bool(
        data.get(
            "is_default",
            False,
        )
    )

    account = Account(
        user_id=user.id,
        name=name,
        account_type=account_type,
        institution=institution,
        balance=balance,
        currency=currency,
        is_default=(
            requested_default
            or not has_active_account
        ),
        is_archived=False,
    )

    db.session.add(account)
    db.session.flush()

    if account.is_default:
        make_default_account(
            user.id,
            account,
        )

    db.session.commit()

    return jsonify({
        "account":
            account.to_dict()
    }), 201


@accounts_bp.patch(
    "/<int:account_id>"
)
@jwt_required()
def update_account(account_id):
    user = current_user()

    account = (
        Account.query.filter_by(
            id=account_id,
            user_id=user.id,
        ).first_or_404()
    )

    data = request.get_json() or {}

    if "name" in data:
        name = (
            data.get("name") or ""
        ).strip()

        if not name:
            return jsonify({
                "error":
                    "Account name cannot be empty."
            }), 400

        duplicate = (
            Account.query.filter(
                Account.user_id == user.id,
                Account.id != account.id,
                db.func.lower(
                    Account.name
                )
                == name.lower(),
                Account.is_archived.is_(
                    False
                ),
            ).first()
        )

        if duplicate:
            return jsonify({
                "error":
                    "You already have an active account with this name."
            }), 409

        account.name = name

    if "account_type" in data:
        account_type = (
            data.get(
                "account_type"
            )
            or ""
        ).strip().lower()

        if (
            account_type
            not in VALID_ACCOUNT_TYPES
        ):
            return jsonify({
                "error":
                    "Invalid account type."
            }), 400

        account.account_type = (
            account_type
        )

    if "institution" in data:
        account.institution = (
            clean_optional_text(
                data.get(
                    "institution"
                )
            )
        )

    if "currency" in data:
        currency = (
            data.get("currency")
            or ""
        ).strip().upper()

        if currency not in VALID_CURRENCIES:
            return jsonify({
                "error":
                    "Unsupported currency."
            }), 400

        account.currency = currency

    if (
        data.get("is_default")
        is True
    ):
        make_default_account(
            user.id,
            account,
        )

    if "is_archived" in data:
        should_archive = bool(
            data.get(
                "is_archived"
            )
        )

        if should_archive:
            account.is_archived = True

            if account.is_default:
                account.is_default = False

                db.session.flush()

                ensure_default_account(
                    user.id
                )

        else:
            account.is_archived = False

            has_default = (
                Account.query.filter_by(
                    user_id=user.id,
                    is_default=True,
                    is_archived=False,
                ).first()
            )

            if not has_default:
                account.is_default = True

    db.session.commit()

    return jsonify({
        "account":
            account.to_dict()
    }), 200


@accounts_bp.delete(
    "/<int:account_id>"
)
@jwt_required()
def delete_account(account_id):
    user = current_user()

    account = (
        Account.query.filter_by(
            id=account_id,
            user_id=user.id,
        ).first_or_404()
    )

    if account.is_archived:
        return jsonify({
            "message":
                "Account is already archived."
        }), 200

    was_default = (
        account.is_default
    )

    account.is_archived = True
    account.is_default = False

    db.session.flush()

    if was_default:
        ensure_default_account(
            user.id
        )

    db.session.commit()

    return jsonify({
        "message":
            "Account archived."
    }), 200