
from datetime import datetime
from app.extensions import db

class Budget(db.Model):
    __tablename__ = "budgets"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category = db.relationship("Category")
    __table_args__ = (db.UniqueConstraint("user_id", "category_id", "month", "year", name="uq_budget_period"),)

    def to_dict(self, spent=0):
        spent, amount = float(spent or 0), float(self.amount or 0)
        return {
            "id": self.id, "category_id": self.category_id,
            "category": self.category.to_dict() if self.category else None,
            "amount": amount, "spent": spent, "remaining": max(amount-spent, 0),
            "percentage": round(spent/amount*100, 1) if amount else 0, "month": self.month, "year": self.year
        }
