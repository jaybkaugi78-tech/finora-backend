
from datetime import date, timedelta

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from ..extensions import db
from ..models import (
    Notification,
    NotificationDismissal,
    Bill,
)
from .common import uid, fail


bp = Blueprint("notifications", __name__)


def reminders(user):
    today = date.today()

    bills = Bill.query.filter_by(
        user_id=user,
        is_active=True,
    ).all()

    created = False

    for bill in bills:
        if bill.next_due_date is None:
            continue

        reminder_days = max(
            int(bill.reminder_days or 0),
            0,
        )

        reminder_date = (
            bill.next_due_date
            - timedelta(days=reminder_days)
        )

        if today < reminder_date:
            continue

        key = (
            f"bill:{bill.id}:"
            f"{bill.next_due_date.isoformat()}"
        )

        dismissed = NotificationDismissal.query.filter_by(
            user_id=user,
            dedupe_key=key,
        ).first()

        if dismissed:
            continue

        existing = Notification.query.filter_by(
            user_id=user,
            dedupe_key=key,
        ).first()

        if existing:
            continue

        overdue = bill.next_due_date < today

        notification = Notification(
            user_id=user,
            title=(
                f"Overdue bill: {bill.name}"
                if overdue
                else f"Bill reminder: {bill.name}"
            ),
            message=(
                f"{bill.name} was due on "
                f"{bill.next_due_date.isoformat()}."
                if overdue
                else f"{bill.name} is due on "
                f"{bill.next_due_date.isoformat()}."
            ),
            notification_type=(
                "bill_overdue"
                if overdue
                else "bill"
            ),
            dedupe_key=key,
        )

        db.session.add(notification)
        created = True

    if created:
        db.session.commit()


@bp.get("/notifications")
@jwt_required()
def listing():
    user = uid()

    reminders(user)

    selected_filter = (
        request.args.get("filter", "all")
        .strip()
        .lower()
    )

    if selected_filter not in ("all", "unread", "read"):
        return fail(
            "Invalid notification filter.",
            400,
        )

    base_query = Notification.query.filter_by(
        user_id=user
    )

    total_count = base_query.count()

    unread_count = base_query.filter_by(
        is_read=False
    ).count()

    query = base_query

    if selected_filter == "unread":
        query = query.filter_by(is_read=False)

    elif selected_filter == "read":
        query = query.filter_by(is_read=True)

    items = (
        query
        .order_by(
            Notification.created_at.desc(),
            Notification.id.desc(),
        )
        .limit(100)
        .all()
    )

    return jsonify(
        notifications=[
            notification.to_dict()
            for notification in items
        ],
        unread_count=unread_count,
        total_count=total_count,
    )


@bp.post("/notifications/read-all")
@jwt_required()
def all_read():
    user = uid()

    updated = (
        Notification.query
        .filter_by(
            user_id=user,
            is_read=False,
        )
        .update(
            {"is_read": True},
            synchronize_session=False,
        )
    )

    db.session.commit()

    return jsonify(
        message="All notifications marked as read.",
        updated_count=updated,
        unread_count=0,
    )


@bp.delete("/notifications/clear-read")
@jwt_required()
def clear():
    user = uid()

    notifications = Notification.query.filter_by(
        user_id=user,
        is_read=True,
    ).all()

    for notification in notifications:
        if notification.dedupe_key:
            remember_dismissal(
                user,
                notification.dedupe_key,
            )

        db.session.delete(notification)

    db.session.commit()

    return jsonify(
        message="Read notifications cleared.",
        deleted_count=len(notifications),
    )


def remember_dismissal(user, dedupe_key):
    existing = NotificationDismissal.query.filter_by(
        user_id=user,
        dedupe_key=dedupe_key,
    ).first()

    if existing:
        return

    db.session.add(
        NotificationDismissal(
            user_id=user,
            dedupe_key=dedupe_key,
        )
    )


@bp.route(
    "/notifications/<int:id>",
    methods=["PATCH", "PUT", "DELETE"],
)
@jwt_required()
def item(id):
    user = uid()

    notification = Notification.query.filter_by(
        user_id=user,
        id=id,
    ).first()

    if notification is None:
        return fail(
            "Notification not found.",
            404,
        )

    if request.method == "DELETE":
        if notification.dedupe_key:
            remember_dismissal(
                user,
                notification.dedupe_key,
            )

        db.session.delete(notification)
        db.session.commit()

        return jsonify(
            message="Notification dismissed.",
            deleted_id=id,
        )

    data = request.get_json(silent=True) or {}

    is_read = data.get("is_read", True)

    if not isinstance(is_read, bool):
        return fail(
            "is_read must be true or false.",
            400,
        )

    notification.is_read = is_read

    db.session.commit()

    return jsonify(
        message=(
            "Notification marked as read."
            if is_read
            else "Notification marked as unread."
        ),
        notification=notification.to_dict(),
    )
