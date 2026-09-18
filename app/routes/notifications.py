from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Bill, Notification
from app.utils.auth import current_user


notifications_bp = Blueprint(
    "notifications",
    __name__,
)


def create_bill_notifications(user):
    today = date.today()

    bills = (
        Bill.query
        .filter_by(
            user_id=user.id,
            is_active=True,
        )
        .order_by(
            Bill.next_due_date.asc()
        )
        .all()
    )

    created = False

    for bill in bills:
        days_until_due = (
            bill.next_due_date
            - today
        ).days

        should_notify = (
            days_until_due
            <= bill.reminder_days
        )

        if not should_notify:
            continue

        due_date_text = (
            bill.next_due_date.isoformat()
        )

        if days_until_due < 0:
            title = (
                f"{bill.name} is overdue"
            )

            days_overdue = abs(
                days_until_due
            )

            message = (
                f"{bill.name} was due on "
                f"{due_date_text} and is "
                f"{days_overdue} day"
                f"{'' if days_overdue == 1 else 's'} "
                f"overdue."
            )

            notification_type = (
                "bill_overdue"
            )

        elif days_until_due == 0:
            title = (
                f"{bill.name} is due today"
            )

            message = (
                f"{bill.name} is due today "
                f"({due_date_text})."
            )

            notification_type = (
                "bill_due"
            )

        elif days_until_due == 1:
            title = (
                f"{bill.name} is due tomorrow"
            )

            message = (
                f"{bill.name} is due tomorrow "
                f"({due_date_text})."
            )

            notification_type = (
                "bill_reminder"
            )

        else:
            title = (
                f"{bill.name} is due soon"
            )

            message = (
                f"{bill.name} is due in "
                f"{days_until_due} days "
                f"({due_date_text})."
            )

            notification_type = (
                "bill_reminder"
            )

        duplicate = (
            Notification.query
            .filter(
                Notification.user_id
                == user.id,

                Notification.notification_type
                == notification_type,

                Notification.title
                == title,

                Notification.message
                == message,
            )
            .first()
        )

        if duplicate:
            continue

        notification = Notification(
            user_id=user.id,
            title=title,
            message=message,
            notification_type=(
                notification_type
            ),
            is_read=False,
        )

        db.session.add(
            notification
        )

        created = True

    if created:
        db.session.commit()


def serialize_notifications(
    notifications,
):
    return [
        notification.to_dict()
        for notification
        in notifications
    ]


@notifications_bp.get("")
@jwt_required()
def list_notifications():
    user = current_user()

    create_bill_notifications(
        user
    )

    filter_type = (
        request.args.get(
            "filter",
            "all",
        )
        .strip()
        .lower()
    )

    query = (
        Notification.query
        .filter_by(
            user_id=user.id
        )
    )

    if filter_type == "unread":
        query = query.filter_by(
            is_read=False
        )

    elif filter_type == "read":
        query = query.filter_by(
            is_read=True
        )

    notifications = (
        query
        .order_by(
            Notification
            .created_at
            .desc()
        )
        .limit(100)
        .all()
    )

    unread_count = (
        Notification.query
        .filter_by(
            user_id=user.id,
            is_read=False,
        )
        .count()
    )

    total_count = (
        Notification.query
        .filter_by(
            user_id=user.id
        )
        .count()
    )

    return jsonify({
        "notifications":
            serialize_notifications(
                notifications
            ),

        "unread_count":
            unread_count,

        "total_count":
            total_count,
    }), 200


@notifications_bp.patch(
    "/<int:notification_id>/read"
)
@jwt_required()
def mark_read(
    notification_id,
):
    user = current_user()

    notification = (
        Notification.query
        .filter_by(
            id=notification_id,
            user_id=user.id,
        )
        .first_or_404()
    )

    notification.is_read = True

    db.session.commit()

    return jsonify({
        "notification":
            notification.to_dict()
    }), 200


@notifications_bp.patch(
    "/<int:notification_id>/unread"
)
@jwt_required()
def mark_unread(
    notification_id,
):
    user = current_user()

    notification = (
        Notification.query
        .filter_by(
            id=notification_id,
            user_id=user.id,
        )
        .first_or_404()
    )

    notification.is_read = False

    db.session.commit()

    return jsonify({
        "notification":
            notification.to_dict()
    }), 200


@notifications_bp.patch(
    "/read-all"
)
@jwt_required()
def mark_all_read():
    user = current_user()

    (
        Notification.query
        .filter_by(
            user_id=user.id,
            is_read=False,
        )
        .update(
            {
                Notification.is_read:
                    True
            },
            synchronize_session=False,
        )
    )

    db.session.commit()

    return jsonify({
        "message":
            "All notifications marked as read."
    }), 200


@notifications_bp.delete(
    "/<int:notification_id>"
)
@jwt_required()
def delete_notification(
    notification_id,
):
    user = current_user()

    notification = (
        Notification.query
        .filter_by(
            id=notification_id,
            user_id=user.id,
        )
        .first_or_404()
    )

    db.session.delete(
        notification
    )

    db.session.commit()

    return jsonify({
        "message":
            "Notification deleted."
    }), 200


@notifications_bp.delete(
    "/read"
)
@jwt_required()
def clear_read_notifications():
    user = current_user()

    deleted = (
        Notification.query
        .filter_by(
            user_id=user.id,
            is_read=True,
        )
        .delete(
            synchronize_session=False
        )
    )

    db.session.commit()

    return jsonify({
        "message":
            "Read notifications cleared.",

        "deleted":
            deleted,
    }), 200