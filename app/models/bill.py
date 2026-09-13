
from datetime import datetime
from app.extensions import db

class Bill(db.Model):
    __tablename__ = "bills"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"))
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"))
    frequency = db.Column(db.String(30), nullable=False, default="monthly")
    next_due_date = db.Column(db.Date, nullable=False, index=True)
    reminder_days = db.Column(db.Integer, nullable=False, default=3)
    is_subscription = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category = db.relationship("Category")
    account = db.relationship("Account")

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "amount": float(self.amount), "category_id": self.category_id,
            "account_id": self.account_id, "frequency": self.frequency, "next_due_date": self.next_due_date.isoformat(),
            "reminder_days": self.reminder_days, "is_subscription": self.is_subscription, "is_active": self.is_active
        }
