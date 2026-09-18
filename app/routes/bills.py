from calendar import monthrange
from datetime import date, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Account, Bill, Category
from app.utils.auth import current_user


bills_bp = Blueprint(
    "bills",
    __name__,
)


VALID_FREQUENCIES = {
    "weekly",
    "monthly",
    "quarterly",
    "yearly",
}


def parse_amount(value):
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError(
            "Amount must be valid."
        )

    if amount <= 0:
        raise ValueError(
            "Amount must be greater than zero."
        )

    return amount


def parse_due_date(value):
    if not value:
        raise ValueError(
            "Due date is required."
        )

    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        raise ValueError(
            "Due date must be valid."
        )


def parse_reminder_days(value):
    try:
        reminder_days = int(value)
    except (TypeError, ValueError):
        raise ValueError(
            "Reminder days must be valid."
        )

    if reminder_days < 0:
        raise ValueError(
            "Reminder days cannot be negative."
        )

    if reminder_days > 365:
        raise ValueError(
            "Reminder days cannot exceed 365."
        )

    return reminder_days


def validate_frequency(value):
    frequency = (
        value or "monthly"
    ).strip().lower()

    if frequency not in VALID_FREQUENCIES:
        raise ValueError(
            "Invalid bill frequency."
        )

    return frequency


def get_user_account(
    user_id,
    account_id,
):
    if account_id in (
        None,
        "",
    ):
        return None

    try:
        account_id = int(
            account_id
        )
    except (TypeError, ValueError):
        raise ValueError(
            "Invalid account."
        )

    account = (
        Account.query
        .filter_by(
            id=account_id,
            user_id=user_id,
        )
        .first()
    )

    if not account:
        raise ValueError(
            "Account not found."
        )

    if account.is_archived:
        raise ValueError(
            "Archived accounts cannot be assigned to bills."
        )

    return account


def get_user_category(
    user_id,
    category_id,
):
    if category_id in (
        None,
        "",
    ):
        return None

    try:
        category_id = int(
            category_id
        )
    except (TypeError, ValueError):
        raise ValueError(
            "Invalid category."
        )

    category = (
        Category.query
        .filter_by(
            id=category_id,
            user_id=user_id,
            category_type="expense",
        )
        .first()
    )

    if not category:
        raise ValueError(
            "Expense category not found."
        )

    return category


def add_months(
    current_date,
    months,
):
    month_index = (
        current_date.month
        - 1
        + months
    )

    year = (
        current_date.year
        + month_index // 12
    )

    month = (
        month_index % 12
        + 1
    )

    day = min(
        current_date.day,
        monthrange(
            year,
            month,
        )[1],
    )

    return date(
        year,
        month,
        day,
    )


def next_due_date(
    current_date,
    frequency,
):
    if frequency == "weekly":
        return (
            current_date
            + timedelta(days=7)
        )

    if frequency == "monthly":
        return add_months(
            current_date,
            1,
        )

    if frequency == "quarterly":
        return add_months(
            current_date,
            3,
        )

    if frequency == "yearly":
        return add_months(
            current_date,
            12,
        )

    raise ValueError(
        "Invalid bill frequency."
    )


def serialize_bill(bill):
    data = bill.to_dict()

    today = date.today()

    days_until_due = (
        bill.next_due_date
        - today
    ).days

    data["days_until_due"] = (
        days_until_due
    )

    data["is_overdue"] = (
        bill.is_active
        and days_until_due < 0
    )

    data["is_due_today"] = (
        bill.is_active
        and days_until_due == 0
    )

    data["is_due_soon"] = (
        bill.is_active
        and 0 < days_until_due
        <= bill.reminder_days
    )

    data["category"] = (
        bill.category.to_dict()
        if bill.category
        else None
    )

    data["account"] = (
        bill.account.to_dict()
        if bill.account
        else None
    )

    return data


@bills_bp.get("")
@jwt_required()
def list_bills():
    user = current_user()

    bills = (
        Bill.query
        .filter_by(
            user_id=user.id
        )
        .order_by(
            Bill.next_due_date.asc()
        )
        .all()
    )

    serialized = [
        serialize_bill(bill)
        for bill in bills
    ]

    active_bills = [
        bill
        for bill in serialized
        if bill["is_active"]
    ]

    upcoming_total = sum(
        bill["amount"]
        for bill in active_bills
    )

    overdue_total = sum(
        bill["amount"]
        for bill in active_bills
        if bill["is_overdue"]
    )

    due_soon_count = sum(
        1
        for bill in active_bills
        if (
            bill["is_due_soon"]
            or bill["is_due_today"]
        )
    )

    subscriptions_total = sum(
        bill["amount"]
        for bill in active_bills
        if bill["is_subscription"]
    )

    return jsonify({
        "bills": serialized,

        "summary": {
            "active_count":
                len(active_bills),

            "upcoming_total":
                upcoming_total,

            "overdue_total":
                overdue_total,

            "due_soon_count":
                due_soon_count,

            "subscriptions_total":
                subscriptions_total,
        },
    }), 200


@bills_bp.post("")
@jwt_required()
def create_bill():
    user = current_user()
    data = request.get_json() or {}

    name = (
        data.get("name")
        or ""
    ).strip()

    if not name:
        return jsonify({
            "error":
                "Bill name is required."
        }), 400

    try:
        amount = parse_amount(
            data.get("amount")
        )

        due_date = parse_due_date(
            data.get(
                "next_due_date"
            )
        )

        frequency = (
            validate_frequency(
                data.get(
                    "frequency"
                )
            )
        )

        reminder_days = (
            parse_reminder_days(
                data.get(
                    "reminder_days",
                    3,
                )
            )
        )

        account = get_user_account(
            user.id,
            data.get(
                "account_id"
            ),
        )

        category = get_user_category(
            user.id,
            data.get(
                "category_id"
            ),
        )

    except ValueError as exc:
        return jsonify({
            "error": str(exc)
        }), 400

    bill = Bill(
        user_id=user.id,
        name=name,
        amount=amount,

        category_id=(
            category.id
            if category
            else None
        ),

        account_id=(
            account.id
            if account
            else None
        ),

        frequency=frequency,
        next_due_date=due_date,
        reminder_days=reminder_days,

        is_subscription=bool(
            data.get(
                "is_subscription",
                False,
            )
        ),

        is_active=True,
    )

    db.session.add(bill)
    db.session.commit()

    return jsonify({
        "bill":
            serialize_bill(bill)
    }), 201


@bills_bp.patch(
    "/<int:bill_id>"
)
@jwt_required()
def update_bill(bill_id):
    user = current_user()

    bill = (
        Bill.query
        .filter_by(
            id=bill_id,
            user_id=user.id,
        )
        .first_or_404()
    )

    data = request.get_json() or {}

    try:
        if "name" in data:
            name = (
                data.get("name")
                or ""
            ).strip()

            if not name:
                raise ValueError(
                    "Bill name is required."
                )

            bill.name = name

        if "amount" in data:
            bill.amount = (
                parse_amount(
                    data.get("amount")
                )
            )

        if "next_due_date" in data:
            bill.next_due_date = (
                parse_due_date(
                    data.get(
                        "next_due_date"
                    )
                )
            )

        if "frequency" in data:
            bill.frequency = (
                validate_frequency(
                    data.get(
                        "frequency"
                    )
                )
            )

        if "reminder_days" in data:
            bill.reminder_days = (
                parse_reminder_days(
                    data.get(
                        "reminder_days"
                    )
                )
            )

        if "category_id" in data:
            category = (
                get_user_category(
                    user.id,
                    data.get(
                        "category_id"
                    ),
                )
            )

            bill.category_id = (
                category.id
                if category
                else None
            )

        if "account_id" in data:
            account = (
                get_user_account(
                    user.id,
                    data.get(
                        "account_id"
                    ),
                )
            )

            bill.account_id = (
                account.id
                if account
                else None
            )

        if "is_subscription" in data:
            bill.is_subscription = bool(
                data.get(
                    "is_subscription"
                )
            )

        if "is_active" in data:
            bill.is_active = bool(
                data.get(
                    "is_active"
                )
            )

    except ValueError as exc:
        return jsonify({
            "error": str(exc)
        }), 400

    db.session.commit()

    return jsonify({
        "bill":
            serialize_bill(bill)
    }), 200


@bills_bp.post(
    "/<int:bill_id>/mark-paid"
)
@jwt_required()
def mark_bill_paid(bill_id):
    user = current_user()

    bill = (
        Bill.query
        .filter_by(
            id=bill_id,
            user_id=user.id,
        )
        .first_or_404()
    )

    if not bill.is_active:
        return jsonify({
            "error":
                "Inactive bills cannot be marked as paid."
        }), 400

    old_due_date = (
        bill.next_due_date
    )

    try:
        bill.next_due_date = (
            next_due_date(
                bill.next_due_date,
                bill.frequency,
            )
        )
    except ValueError as exc:
        return jsonify({
            "error": str(exc)
        }), 400

    db.session.commit()

    return jsonify({
        "message":
            "Bill marked as paid.",

        "previous_due_date":
            old_due_date.isoformat(),

        "bill":
            serialize_bill(bill),
    }), 200


@bills_bp.delete(
    "/<int:bill_id>"
)
@jwt_required()
def delete_bill(bill_id):
    user = current_user()

    bill = (
        Bill.query
        .filter_by(
            id=bill_id,
            user_id=user.id,
        )
        .first_or_404()
    )

    db.session.delete(bill)
    db.session.commit()

    return jsonify({
        "message":
            "Bill deleted."
    }), 200