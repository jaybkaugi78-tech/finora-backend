from datetime import datetime, date
from decimal import Decimal
from werkzeug.security import generate_password_hash, check_password_hash
from .extensions import db

def money(value):
    return float(value or 0)

class User(db.Model):
    __tablename__='users'
    id=db.Column(db.Integer, primary_key=True)
    full_name=db.Column(db.String(160), nullable=False)
    email=db.Column(db.String(255), nullable=False, unique=True, index=True)
    password_hash=db.Column(db.String(255), nullable=False)
    currency=db.Column(db.String(3), nullable=False, default='KES')
    country=db.Column(db.String(80), default='Kenya')
    timezone=db.Column(db.String(80), default='Africa/Nairobi')
    created_at=db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    def set_password(self, p): self.password_hash=generate_password_hash(p)
    def check_password(self,p): return check_password_hash(self.password_hash,p)
    def to_dict(self): return dict(id=self.id, full_name=self.full_name, email=self.email, currency=self.currency, country=self.country, timezone=self.timezone)

class Account(db.Model):
    __tablename__='accounts'
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False,index=True)
    name=db.Column(db.String(120),nullable=False)
    account_type=db.Column(db.String(50),nullable=False)
    institution=db.Column(db.String(120))
    opening_balance=db.Column(db.Numeric(14,2),nullable=False,default=0)
    balance=db.Column(db.Numeric(14,2),nullable=False,default=0)
    currency=db.Column(db.String(3),nullable=False,default='KES')
    is_default=db.Column(db.Boolean,nullable=False,default=False)
    is_archived=db.Column(db.Boolean,nullable=False,default=False)
    created_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False)
    def to_dict(self): return dict(id=self.id,name=self.name,account_type=self.account_type,institution=self.institution,balance=money(self.balance),opening_balance=money(self.opening_balance),currency=self.currency,is_default=self.is_default,is_archived=self.is_archived)

class Category(db.Model):
    __tablename__='categories'
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False,index=True)
    name=db.Column(db.String(100),nullable=False)
    category_type=db.Column(db.String(20),nullable=False,default='expense')
    __table_args__=(db.UniqueConstraint('user_id','name','category_type'),)
    def to_dict(self): return dict(id=self.id,name=self.name,category_type=self.category_type,type=self.category_type)

class Transaction(db.Model):
    __tablename__='transactions'
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False,index=True)
    transaction_type=db.Column(db.String(20),nullable=False)
    amount=db.Column(db.Numeric(14,2),nullable=False)
    account_id=db.Column(db.Integer,db.ForeignKey('accounts.id'),nullable=False,index=True)
    destination_account_id=db.Column(db.Integer,db.ForeignKey('accounts.id'))
    category_id=db.Column(db.Integer,db.ForeignKey('categories.id'))
    merchant=db.Column(db.String(160))
    description=db.Column(db.String(255))
    notes=db.Column(db.Text)
    transaction_date=db.Column(db.DateTime,nullable=False,default=datetime.utcnow,index=True)
    is_recurring=db.Column(db.Boolean,default=False,nullable=False)
    created_at=db.Column(db.DateTime,default=datetime.utcnow,nullable=False)
    updated_at=db.Column(db.DateTime,default=datetime.utcnow,onupdate=datetime.utcnow,nullable=False)
    category=db.relationship('Category')
    def to_dict(self): return dict(id=self.id,transaction_type=self.transaction_type,amount=money(self.amount),account_id=self.account_id,destination_account_id=self.destination_account_id,category_id=self.category_id,category=self.category.to_dict() if self.category else None,merchant=self.merchant,description=self.description,notes=self.notes,transaction_date=self.transaction_date.isoformat(),is_recurring=self.is_recurring)

class Budget(db.Model):
    __tablename__='budgets'
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False,index=True)
    category_id=db.Column(db.Integer,db.ForeignKey('categories.id'),nullable=False)
    amount=db.Column(db.Numeric(14,2),nullable=False)
    month=db.Column(db.Integer,nullable=False)
    year=db.Column(db.Integer,nullable=False)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    category=db.relationship('Category')
    __table_args__=(db.UniqueConstraint('user_id','category_id','month','year'),)

class Goal(db.Model):
    __tablename__='goals'
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False,index=True)
    name=db.Column(db.String(160),nullable=False)
    target_amount=db.Column(db.Numeric(14,2),nullable=False)
    target_date=db.Column(db.Date)
    notes=db.Column(db.Text)
    is_completed=db.Column(db.Boolean,nullable=False,default=False)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    contributions=db.relationship('GoalContribution',cascade='all, delete-orphan',lazy='selectin')
    def to_dict(self):
        saved=sum((c.amount for c in self.contributions),Decimal('0'))
        pct=float(saved/self.target_amount*100) if self.target_amount else 0
        return dict(id=self.id,name=self.name,target_amount=money(self.target_amount),target_date=self.target_date.isoformat() if self.target_date else None,notes=self.notes,is_completed=self.is_completed,saved_amount=money(saved),remaining=max(money(self.target_amount-saved),0),percentage=round(pct,1),created_at=self.created_at.isoformat())

class GoalContribution(db.Model):
    __tablename__='goal_contributions'
    id=db.Column(db.Integer,primary_key=True)
    goal_id=db.Column(db.Integer,db.ForeignKey('goals.id'),nullable=False,index=True)
    amount=db.Column(db.Numeric(14,2),nullable=False)
    note=db.Column(db.String(255))
    contributed_at=db.Column(db.DateTime,default=datetime.utcnow)
    def to_dict(self): return dict(id=self.id,goal_id=self.goal_id,amount=money(self.amount),note=self.note,contributed_at=self.contributed_at.isoformat())

class Bill(db.Model):
    __tablename__='bills'
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False,index=True)
    name=db.Column(db.String(160),nullable=False)
    amount=db.Column(db.Numeric(14,2),nullable=False)
    category_id=db.Column(db.Integer,db.ForeignKey('categories.id'))
    account_id=db.Column(db.Integer,db.ForeignKey('accounts.id'))
    frequency=db.Column(db.String(20),nullable=False,default='monthly')
    next_due_date=db.Column(db.Date,nullable=False)
    reminder_days=db.Column(db.Integer,nullable=False,default=3)
    is_subscription=db.Column(db.Boolean,nullable=False,default=False)
    is_active=db.Column(db.Boolean,nullable=False,default=True)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    def to_dict(self): return dict(id=self.id,name=self.name,amount=money(self.amount),category_id=self.category_id,account_id=self.account_id,frequency=self.frequency,next_due_date=self.next_due_date.isoformat(),reminder_days=self.reminder_days,is_subscription=self.is_subscription,is_active=self.is_active)

class Notification(db.Model):
    __tablename__='notifications'
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False,index=True)
    title=db.Column(db.String(160),nullable=False)
    message=db.Column(db.Text,nullable=False)
    notification_type=db.Column(db.String(30),default='info')
    is_read=db.Column(db.Boolean,nullable=False,default=False)
    dedupe_key=db.Column(db.String(160))
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    __table_args__=(db.UniqueConstraint('user_id','dedupe_key'),)
    def to_dict(self): return dict(id=self.id,title=self.title,message=self.message,notification_type=self.notification_type,is_read=self.is_read,created_at=self.created_at.isoformat())

class IdempotencyKey(db.Model):
    __tablename__='idempotency_keys'
    id=db.Column(db.Integer,primary_key=True)
    user_id=db.Column(db.Integer,db.ForeignKey('users.id'),nullable=False)
    key=db.Column(db.String(128),nullable=False)
    payload_hash=db.Column(db.String(64),nullable=False)
    response_json=db.Column(db.JSON,nullable=False)
    created_at=db.Column(db.DateTime,default=datetime.utcnow)
    __table_args__=(db.UniqueConstraint('user_id','key'),)


class NotificationDismissal(db.Model):
    __tablename__ = "notification_dismissals"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    dedupe_key = db.Column(
        db.String(255),
        nullable=False,
    )

    dismissed_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "dedupe_key",
            name="uq_notification_dismissal_user_key",
        ),
    )

from datetime import datetime, timezone


class RevokedToken(db.Model):
    __tablename__ = "revoked_tokens"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    jti = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        index=True,
    )

    token_type = db.Column(
        db.String(20),
        nullable=False,
    )

    revoked_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    expires_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
    )
