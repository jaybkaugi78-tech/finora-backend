from datetime import date,timedelta
from flask import Blueprint,jsonify,request
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from ..extensions import db
from ..models import Account,Transaction,Budget,Bill,Goal,Notification,Category
from ..services.finance import totals,month_bounds,reconcile
from .common import uid,fail
from .budgets import serialize as budget_dict
bp=Blueprint('analytics',__name__)
def scoped_accounts(user):
    return Account.query.filter_by(user_id=user,is_archived=False).order_by(Account.created_at.desc()).all()
def currency_total(user):
    accounts=scoped_accounts(user);currencies={a.currency for a in accounts}
    if len(currencies)>1:return None
    return round(sum(float(a.balance) for a in accounts),2)
@bp.get('/analytics/dashboard')
@jwt_required()
def dashboard():
    user=uid();today=date.today();income,expenses=totals(user,today.year,today.month)
    accounts=scoped_accounts(user);bal=currency_total(user)
    bills=Bill.query.filter(Bill.user_id==user,Bill.is_active.is_(True),Bill.next_due_date>=today,Bill.next_due_date<=today+timedelta(days=30)).order_by(Bill.next_due_date).all()
    upcoming=sum(float(b.amount) for b in bills)
    budgets=[budget_dict(b) for b in Budget.query.filter_by(user_id=user,month=today.month,year=today.year).all()]
    spent=sum(b['spent'] for b in budgets);budgeted=sum(b['amount'] for b in budgets)
    start,end=month_bounds(today.year,today.month)
    txs=Transaction.query.filter_by(user_id=user).order_by(Transaction.transaction_date.desc(),Transaction.id.desc()).limit(5).all()
    return jsonify(available_balance=bal,balance_currency=accounts[0].currency if accounts and bal is not None else None,mixed_currencies=bal is None,safe_to_spend=max(bal-upcoming,0) if bal is not None else None,income_this_month=income,expenses_this_month=expenses,net_cash_flow=income-expenses,savings_rate=round((income-expenses)/income*100,1) if income else 0,upcoming_bills=upcoming,transaction_count=Transaction.query.filter(Transaction.user_id==user,Transaction.transaction_date>=start,Transaction.transaction_date<end).count(),unread_notifications=Notification.query.filter_by(user_id=user,is_read=False).count(),recent_transactions=[t.to_dict() for t in txs],accounts=[a.to_dict() for a in accounts[:4]],upcoming_bill_items=[dict(**b.to_dict(),days_until_due=(b.next_due_date-today).days) for b in bills[:4]],goals=[g.to_dict() for g in Goal.query.filter_by(user_id=user,is_completed=False).limit(3)],budgets=budgets[:4],budget_summary=dict(total_budget=budgeted,spent=spent,remaining=budgeted-spent,percentage=round(spent/budgeted*100,1) if budgeted else 0))
@bp.get('/analytics/summary')
@jwt_required()
def summary():
    d=date.today();i,e=totals(uid(),int(request.args.get('year',d.year)),int(request.args.get('month',d.month)))
    return jsonify(income=i,expenses=e,net=i-e,available_balance=currency_total(uid()))
@bp.get('/analytics/monthly-trend')
@jwt_required()
def trend():
    today=date.today();rows=[]
    for offset in range(5,-1,-1):
        n=today.year*12+today.month-1-offset;y=(n//12);m=n%12+1;i,e=totals(uid(),y,m)
        rows.append(dict(month=f'{y}-{m:02d}',income=i,expenses=e,net=i-e))
    return jsonify(trend=rows,monthly_trend=rows)
@bp.get('/analytics/spending-by-category')
@jwt_required()
def spending():
    today=date.today();year=int(request.args.get('year',today.year));month=int(request.args.get('month',today.month))
    start,end=month_bounds(year,month)
    rows=db.session.query(Category.name,func.sum(Transaction.amount)).join(Transaction,Transaction.category_id==Category.id).filter(Transaction.user_id==uid(),Transaction.transaction_type=='expense',Transaction.transaction_date>=start,Transaction.transaction_date<end).group_by(Category.name).all()
    data=[dict(category=name,name=name,amount=float(value),total=float(value)) for name,value in rows]
    return jsonify(categories=data,spending_by_category=data)
@bp.get('/analytics/accounts')
@jwt_required()
def accounts():return jsonify(accounts=[a.to_dict() for a in scoped_accounts(uid())],total=currency_total(uid()))
@bp.get('/analytics/insights')
@jwt_required()
def insights():
    today=date.today();i,e=totals(uid(),today.year,today.month)
    return jsonify(insights=[{'title':'Monthly cash flow','message':f'Income {i:.2f}; expenses {e:.2f}; net {i-e:.2f}.'}])
@bp.get('/analytics/reconcile')
@jwt_required()
def audit():
    rows=reconcile(uid());return jsonify(accounts=rows,all_match=all(r['matches'] for r in rows))
