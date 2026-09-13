
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db

class User(db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    currency = db.Column(db.String(10), nullable=False, default="KES")
    country = db.Column(db.String(80), default="Kenya")
    timezone = db.Column(db.String(80), nullable=False, default="Africa/Nairobi")
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    accounts = db.relationship("Account", backref="user", lazy=True, cascade="all, delete-orphan")
    categories = db.relationship("Category", backref="user", lazy=True, cascade="all, delete-orphan")
    transactions = db.relationship("Transaction", backref="user", lazy=True, cascade="all, delete-orphan")
    budgets = db.relationship("Budget", backref="user", lazy=True, cascade="all, delete-orphan")
    goals = db.relationship("Goal", backref="user", lazy=True, cascade="all, delete-orphan")
    bills = db.relationship("Bill", backref="user", lazy=True, cascade="all, delete-orphan")

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id, "full_name": self.full_name, "email": self.email,
            "currency": self.currency, "country": self.country, "timezone": self.timezone,
            "created_at": self.created_at.isoformat()
        }
