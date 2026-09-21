from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func

from app.extensions import db
from app.models import Account, Bill, Transaction


def account_total(user_id):
    """
    Return the combined balance of all active
    (non-archived) accounts belonging to the user.
    """

    total = (
        db.session.query(
            func.coalesce(
                func.sum(Account.balance),
                0,
            )
        )
        .filter(
            Account.user_id == user_id,
            Account.is_archived.is_(False),
        )
        .scalar()
    )

    return float(total or 0)


def month_bounds(year, month):
    """
    Return the start of a month and the start
    of the following month.

    Example:
    September 2026
    -> 2026-09-01
    -> 2026-10-01
    """

    start = datetime(
        year,
        month,
        1,
    )

    if month == 12:
        end = datetime(
            year + 1,
            1,
            1,
        )
    else:
        end = datetime(
            year,
            month + 1,
            1,
        )

    return start, end


def month_totals(
    user_id,
    year,
    month,
):
    """
    Calculate total income and expenses
    for a specific month.

    Transfers are intentionally excluded.
    """

    start, end = month_bounds(
        year,
        month,
    )

    def total_for(
        transaction_type,
    ):
        total = (
            db.session.query(
                func.coalesce(
                    func.sum(
                        Transaction.amount
                    ),
                    0,
                )
            )
            .filter(
                Transaction.user_id
                == user_id,

                Transaction.transaction_type
                == transaction_type,

                Transaction.transaction_date
                >= start,

                Transaction.transaction_date
                < end,
            )
            .scalar()
        )

        return float(
            total or 0
        )

    income = total_for(
        "income"
    )

    expenses = total_for(
        "expense"
    )

    return income, expenses


def upcoming_bills_total(
    user_id,
    days=30,
):
    """
    Calculate the value of active bills due
    between today and the selected number
    of days in the future.

    Overdue bills are not included here.
    """

    today = date.today()

    cutoff = (
        today
        + timedelta(days=days)
    )

    total = (
        db.session.query(
            func.coalesce(
                func.sum(Bill.amount),
                0,
            )
        )
        .filter(
            Bill.user_id == user_id,

            Bill.is_active.is_(True),

            Bill.next_due_date
            >= today,

            Bill.next_due_date
            <= cutoff,
        )
        .scalar()
    )

    return float(
        total or 0
    )


def safe_to_spend(
    user_id,
):
    """
    Estimate money available after active
    bills due within the next 30 days.

    Safe-to-spend is never returned below 0.
    """

    balance = account_total(
        user_id
    )

    bills = upcoming_bills_total(
        user_id,
        30,
    )

    safe_amount = max(
        balance - bills,
        0,
    )

    return {
        "balance":
            round(
                balance,
                2,
            ),

        "upcoming_bills":
            round(
                bills,
                2,
            ),

        "safe_to_spend":
            round(
                safe_amount,
                2,
            ),
    }


def apply_transaction_to_accounts(
    transaction,
    reverse=False,
):
    """
    Apply a transaction to its associated
    account balances.

    Normal:
        income   -> add to source
        expense  -> subtract from source
        transfer -> subtract source,
                    add destination

    Reverse:
        income   -> subtract from source
        expense  -> add to source
        transfer -> add source,
                    subtract destination

    Reversal is used when editing or deleting
    an existing transaction.
    """

    multiplier = (
        Decimal("-1")
        if reverse
        else Decimal("1")
    )

    amount = Decimal(
        transaction.amount
    )

    if amount <= 0:
        raise ValueError(
            "Transaction amount must be greater than zero."
        )

    source = (
        Account.query
        .filter_by(
            id=transaction.account_id,
            user_id=transaction.user_id,
        )
        .first()
    )

    if not source:
        raise ValueError(
            "Source account not found."
        )

    if (
        transaction.transaction_type
        == "expense"
    ):
        source.balance -= (
            multiplier
            * amount
        )

    elif (
        transaction.transaction_type
        == "income"
    ):
        source.balance += (
            multiplier
            * amount
        )

    elif (
        transaction.transaction_type
        == "transfer"
    ):
        if (
            not transaction
            .destination_account_id
        ):
            raise ValueError(
                "Destination account is required for a transfer."
            )

        if (
            transaction.account_id
            ==
            transaction.destination_account_id
        ):
            raise ValueError(
                "Source and destination accounts cannot be the same."
            )

        destination = (
            Account.query
            .filter_by(
                id=transaction
                .destination_account_id,

                user_id=transaction.user_id,
            )
            .first()
        )

        if not destination:
            raise ValueError(
                "Destination account not found."
            )

        source.balance -= (
            multiplier
            * amount
        )

        destination.balance += (
            multiplier
            * amount
        )

    else:
        raise ValueError(
            "Invalid transaction type."
        )