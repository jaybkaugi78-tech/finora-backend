
from app.extensions import db
from app.models import Category

EXPENSE_CATEGORIES = [
    ("Food", "utensils"), ("Transport", "car"), ("Rent", "house"),
    ("School", "graduation-cap"), ("Shopping", "shopping-bag"),
    ("Entertainment", "gamepad"), ("Airtime & Data", "smartphone"),
    ("Subscriptions", "repeat"), ("Health", "heart-pulse"),
    ("Utilities", "lightbulb"), ("Personal Care", "sparkles"),
    ("Travel", "plane"), ("Other", "circle"),
]

INCOME_CATEGORIES = [
    ("Allowance", "wallet"), ("Salary", "briefcase"), ("Freelance", "laptop"),
    ("Business", "store"), ("Gift", "gift"), ("Investment", "trending-up"),
    ("Refund", "rotate-ccw"), ("Other Income", "circle-plus"),
]

def create_default_categories(user_id):
    items = []
    for name, icon in EXPENSE_CATEGORIES:
        items.append(Category(user_id=user_id, name=name, category_type="expense", icon=icon, is_default=True))
    for name, icon in INCOME_CATEGORIES:
        items.append(Category(user_id=user_id, name=name, category_type="income", icon=icon, is_default=True))
    db.session.add_all(items)
