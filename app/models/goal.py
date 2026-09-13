
from datetime import datetime
from app.extensions import db

class Goal(db.Model):
    __tablename__ = "goals"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(140), nullable=False)
    target_amount = db.Column(db.Numeric(14, 2), nullable=False)
    target_date = db.Column(db.Date)
    notes = db.Column(db.Text)
    is_completed = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    contributions = db.relationship("GoalContribution", backref="goal", lazy=True, cascade="all, delete-orphan")

    def current_amount(self): return sum(float(c.amount) for c in self.contributions)
    def to_dict(self):
        saved, target = self.current_amount(), float(self.target_amount)
        return {
            "id": self.id, "name": self.name, "target_amount": target, "saved_amount": saved,
            "remaining": max(target-saved, 0), "percentage": round(saved/target*100, 1) if target else 0,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "notes": self.notes, "is_completed": self.is_completed
        }
