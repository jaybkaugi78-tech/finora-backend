from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Account, Category, Transaction
from app.services.finance_service import apply_transaction_to_accounts
from app.utils.auth import current_user


transactions_bp = Blueprint("transactions", __name__)

VALID_TYPES = {
    "income",
    "expense",
    "transfer",
}


def parse_date(value):
    if not value:
        return datetime.utcnow()

    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).replace(tzinfo=None)


def get_user_account(account_id, user_id):
    if not account_id:
        return None

    return Account.query.filter_by(
        id=account_id,
        user_id=user_id,
    ).first()


def get_user_category(category_id, user_id):
    if not category_id:
        return None

    return Category.query.filter_by(
        id=category_id,
        user_id=user_id,
    ).first()


def validate_transaction_accounts(
    user,
    kind,
    account_id,
    destination_account_id=None,
):
    source = get_user_account(
        account_id,
        user.id,
    )

    if not source:
        raise ValueError("Account not found.")

    destination = None

    if kind == "transfer":
        destination = get_user_account(
            destination_account_id,
            user.id,
        )

        if not destination:
            raise ValueError(
                "Destination account not found."
            )

        if destination.id == source.id:
            raise ValueError(
                "Transfer accounts must be different."
            )

    return source, destination


@transactions_bp.get("")
@jwt_required()
def list_transactions():
    user = current_user()

    query = Transaction.query.filter_by(
        user_id=user.id
    )

    transaction_type = request.args.get("type")
    category_id = request.args.get("category_id")
    account_id = request.args.get("account_id")
    search = request.args.get("search")

    if transaction_type:
        query = query.filter_by(
            transaction_type=transaction_type
        )

    if category_id:
        try:
            query = query.filter_by(
                category_id=int(category_id)
            )
        except ValueError:
            return jsonify({
                "error": "Invalid category."
            }), 400

    if account_id:
        try:
            account_id = int(account_id)
        except ValueError:
            return jsonify({
                "error": "Invalid account."
            }), 400

        query = query.filter(
            db.or_(
                Transaction.account_id == account_id,
                Transaction.destination_account_id
                == account_id,
            )
        )

    if search:
        pattern = f"%{search.strip()}%"

        query = query.filter(
            db.or_(
                Transaction.merchant.ilike(pattern),
                Transaction.description.ilike(pattern),
                Transaction.notes.ilike(pattern),
            )
        )

    transactions = (
        query
        .order_by(
            Transaction.transaction_date.desc(),
            Transaction.id.desc(),
        )
        .all()
    )

    return jsonify({
        "transactions": [
            transaction.to_dict()
            for transaction in transactions
        ]
    }), 200


@transactions_bp.post("")
@jwt_required()
def create_transaction():
    user = current_user()
    data = request.get_json() or {}

    kind = (
        data.get("transaction_type") or ""
    ).strip().lower()

    if kind not in VALID_TYPES:
        return jsonify({
            "error": "Invalid transaction type."
        }), 400

    try:
        amount = float(data.get("amount"))

        if amount <= 0:
            raise ValueError(
                "Amount must be greater than zero."
            )

        source, destination = (
            validate_transaction_accounts(
                user=user,
                kind=kind,
                account_id=data.get("account_id"),
                destination_account_id=data.get(
                    "destination_account_id"
                ),
            )
        )

        category_id = None

        if kind != "transfer":
            category = get_user_category(
                data.get("category_id"),
                user.id,
            )

            if not category:
                raise ValueError(
                    "Category not found."
                )

            if category.category_type != kind:
                raise ValueError(
                    f"Please select an {kind} category."
                )

            category_id = category.id

        transaction = Transaction(
            user_id=user.id,
            transaction_type=kind,
            amount=amount,
            account_id=source.id,
            destination_account_id=(
                destination.id
                if destination
                else None
            ),
            category_id=category_id,
            merchant=(
                data.get("merchant") or ""
            ).strip() or None,
            description=(
                data.get("description") or ""
            ).strip() or None,
            notes=(
                data.get("notes") or ""
            ).strip() or None,
            transaction_date=parse_date(
                data.get("transaction_date")
            ),
            is_recurring=bool(
                data.get("is_recurring", False)
            ),
        )

        db.session.add(transaction)
        db.session.flush()

        apply_transaction_to_accounts(
            transaction
        )

        db.session.commit()

        return jsonify({
            "transaction": transaction.to_dict()
        }), 201

    except (ValueError, TypeError) as exc:
        db.session.rollback()

        return jsonify({
            "error": str(exc)
        }), 400


@transactions_bp.get("/<int:transaction_id>")
@jwt_required()
def get_transaction(transaction_id):
    user = current_user()

    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=user.id,
    ).first_or_404()

    return jsonify({
        "transaction": transaction.to_dict()
    }), 200


@transactions_bp.patch("/<int:transaction_id>")
@jwt_required()
def update_transaction(transaction_id):
    user = current_user()

    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=user.id,
    ).first_or_404()

    data = request.get_json() or {}

    try:
        # First undo the ORIGINAL transaction.
        apply_transaction_to_accounts(
            transaction,
            reverse=True,
        )

        kind = (
            data.get(
                "transaction_type",
                transaction.transaction_type,
            )
            or ""
        ).strip().lower()

        if kind not in VALID_TYPES:
            raise ValueError(
                "Invalid transaction type."
            )

        amount = float(
            data.get(
                "amount",
                transaction.amount,
            )
        )

        if amount <= 0:
            raise ValueError(
                "Amount must be greater than zero."
            )

        account_id = data.get(
            "account_id",
            transaction.account_id,
        )

        destination_account_id = data.get(
            "destination_account_id",
            transaction.destination_account_id,
        )

        source, destination = (
            validate_transaction_accounts(
                user=user,
                kind=kind,
                account_id=account_id,
                destination_account_id=(
                    destination_account_id
                    if kind == "transfer"
                    else None
                ),
            )
        )

        category_id = None

        if kind != "transfer":
            requested_category_id = data.get(
                "category_id",
                transaction.category_id,
            )

            category = get_user_category(
                requested_category_id,
                user.id,
            )

            if not category:
                raise ValueError(
                    "Category not found."
                )

            if category.category_type != kind:
                raise ValueError(
                    f"Please select an {kind} category."
                )

            category_id = category.id

        transaction.transaction_type = kind
        transaction.amount = amount
        transaction.account_id = source.id
        transaction.destination_account_id = (
            destination.id
            if destination
            else None
        )
        transaction.category_id = category_id

        if "merchant" in data:
            transaction.merchant = (
                data.get("merchant") or ""
            ).strip() or None

        if "description" in data:
            transaction.description = (
                data.get("description") or ""
            ).strip() or None

        if "notes" in data:
            transaction.notes = (
                data.get("notes") or ""
            ).strip() or None

        if "transaction_date" in data:
            transaction.transaction_date = (
                parse_date(
                    data.get("transaction_date")
                )
            )

        if "is_recurring" in data:
            transaction.is_recurring = bool(
                data.get("is_recurring")
            )

        # Apply the NEW version.
        apply_transaction_to_accounts(
            transaction
        )

        db.session.commit()

        return jsonify({
            "transaction": transaction.to_dict()
        }), 200

    except (ValueError, TypeError) as exc:
        db.session.rollback()

        return jsonify({
            "error": str(exc)
        }), 400


@transactions_bp.delete("/<int:transaction_id>")
@jwt_required()
def delete_transaction(transaction_id):
    user = current_user()

    transaction = Transaction.query.filter_by(
        id=transaction_id,
        user_id=user.id,
    ).first_or_404()

    try:
        apply_transaction_to_accounts(
            transaction,
            reverse=True,
        )

        db.session.delete(transaction)
        db.session.commit()

        return jsonify({
            "message": "Transaction deleted."
        }), 200

    except ValueError as exc:
        db.session.rollback()

        return jsonify({
            "error": str(exc)
        }), 400