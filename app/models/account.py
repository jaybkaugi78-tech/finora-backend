
from datetime import datetime
from app.extensions import db

class Account(db.Model):
    __tablename__ = "accounts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    account_type = db.Column(db.String(50), nullable=False)
    institution = db.Column(db.String(120))
    balance = db.Column(db.Numeric(14, 2), nullable=False, default=0)
    currency = db.Column(db.String(10), nullable=False, default="KES")
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    is_archived = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "name": self.name, "account_type": self.account_type,
            "institution": self.institution, "balance": float(self.balance or 0),
            "currency": self.currency, "is_default": self.is_default, "is_archived": self.is_archived
        }
