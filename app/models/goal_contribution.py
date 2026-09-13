
from datetime import datetime
from app.extensions import db

class GoalContribution(db.Model):
    __tablename__ = "goal_contributions"
    id = db.Column(db.Integer, primary_key=True)
    goal_id = db.Column(db.Integer, db.ForeignKey("goals.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    note = db.Column(db.String(255))
    contributed_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    def to_dict(self):
        return {"id": self.id, "amount": float(self.amount), "note": self.note, "contributed_at": self.contributed_at.isoformat()}
