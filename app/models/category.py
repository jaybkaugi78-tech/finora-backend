
from datetime import datetime
from app.extensions import db

class Category(db.Model):
    __tablename__ = "categories"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    category_type = db.Column(db.String(20), nullable=False)
    icon = db.Column(db.String(80))
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "name", "category_type", name="uq_user_category"),)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "category_type": self.category_type, "icon": self.icon, "is_default": self.is_default}
