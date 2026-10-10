
from app.extensions import db
from app.models import Category

DEFAULT_CATEGORIES = {
    "expense": [
        "Food & Groceries",
        "Transport",
        "Shopping",
        "Bills & Utilities",
        "Entertainment",
        "Healthcare",
        "Education",
        "Rent & Housing",
        "Personal Care",
        "Subscriptions",
        "Travel",
        "Other Expenses",
    ],
    "income": [
        "Salary",
        "Freelance",
        "Business",
        "Gifts Received",
        "Investments",
        "Refunds",
        "Other Income",
    ],
}


def create_default_categories(user_id):
    """
    Add default categories for a user.

    Does not commit: the calling function controls
    the database transaction.
    """
    existing = {
        (category.name, category.category_type)
        for category in Category.query.filter_by(
            user_id=user_id
        ).all()
    }

    created = 0

    for category_type, names in DEFAULT_CATEGORIES.items():
        for name in names:
            if (name, category_type) in existing:
                continue

            db.session.add(
                Category(
                    user_id=user_id,
                    name=name,
                    category_type=category_type,
                )
            )

            existing.add((name, category_type))
            created += 1

    return created
