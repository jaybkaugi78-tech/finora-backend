
from datetime import datetime
from app.extensions import db

class Transaction(db.Model):
    __tablename__ = "transactions"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    transaction_type = db.Column(db.String(20), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)
    destination_account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), index=True)
    merchant = db.Column(db.String(160))
    description = db.Column(db.String(255))
    notes = db.Column(db.Text)
    transaction_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    is_recurring = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    account = db.relationship("Account", foreign_keys=[account_id])
    destination_account = db.relationship("Account", foreign_keys=[destination_account_id])
    category = db.relationship("Category")
    attachments = db.relationship("Attachment", backref="transaction", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id, "transaction_type": self.transaction_type, "amount": float(self.amount),
            "account_id": self.account_id, "destination_account_id": self.destination_account_id,
            "category_id": self.category_id, "category": self.category.to_dict() if self.category else None,
            "merchant": self.merchant, "description": self.description, "notes": self.notes,
            "transaction_date": self.transaction_date.isoformat(), "is_recurring": self.is_recurring
        }
