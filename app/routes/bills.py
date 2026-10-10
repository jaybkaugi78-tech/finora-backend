from datetime import date,timedelta
import calendar
from flask import Blueprint,jsonify,request
from flask_jwt_extended import jwt_required
from ..extensions import db
from ..models import Bill
from ..services.finance import amount
from .common import uid,body,fail,parse_date,account_for,category_for
bp=Blueprint('bills',__name__)
def advance(d,f):
    if f=='daily':return d+timedelta(days=1)
    if f=='weekly':return d+timedelta(days=7)
    if f=='yearly':return d.replace(year=d.year+1,day=min(d.day,calendar.monthrange(d.year+1,d.month)[1]))
    m=d.month+1;y=d.year
    if m==13:m=1;y+=1
    return d.replace(year=y,month=m,day=min(d.day,calendar.monthrange(y,m)[1]))
@bp.get('/bills')
@jwt_required()
def listing():return jsonify(bills=[b.to_dict() for b in Bill.query.filter_by(user_id=uid()).order_by(Bill.next_due_date)])
@bp.post('/bills')
@jwt_required()
def create():
    d=body()
    try:
        if not str(d.get('name','')).strip():raise ValueError('Bill name required.')
        if d.get('account_id'):account_for(uid(),int(d['account_id']))
        if d.get('category_id'):category_for(uid(),int(d['category_id']))
        f=d.get('frequency','monthly')
        if f not in ('daily','weekly','monthly','yearly'):raise ValueError('Invalid frequency.')
        b=Bill(user_id=uid(),name=d['name'].strip(),amount=amount(d.get('amount')),category_id=d.get('category_id'),account_id=d.get('account_id'),frequency=f,next_due_date=parse_date(d.get('next_due_date')),reminder_days=int(d.get('reminder_days',3)),is_subscription=bool(d.get('is_subscription',False)))
        db.session.add(b);db.session.commit();return jsonify(bill=b.to_dict()),201
    except (ValueError,TypeError) as e:db.session.rollback();return fail(e)
@bp.route('/bills/<int:id>',methods=['GET','PATCH','PUT','DELETE'])
@jwt_required()
def item(id):
    b=Bill.query.filter_by(id=id,user_id=uid()).first()
    if not b:return fail('Bill not found.',404)
    if request.method=='GET':return jsonify(bill=b.to_dict())
    try:
        if request.method=='DELETE':db.session.delete(b);db.session.commit();return jsonify(message='Bill deleted.')
        d=body()
        for k in ('name','frequency','is_active','is_subscription','reminder_days','account_id','category_id'):
            if k in d:setattr(b,k,d[k])
        if b.frequency not in ('daily','weekly','monthly','yearly'):raise ValueError('Invalid frequency.')
        if b.account_id:account_for(uid(),int(b.account_id))
        if b.category_id:category_for(uid(),int(b.category_id))
        if 'amount' in d:b.amount=amount(d['amount'])
        if 'next_due_date' in d:b.next_due_date=parse_date(d['next_due_date'])
        db.session.commit();return jsonify(bill=b.to_dict())
    except (ValueError,TypeError) as e:db.session.rollback();return fail(e)
@bp.post('/bills/<int:id>/pay')
@jwt_required()
def pay(id):
    b=Bill.query.filter_by(id=id,user_id=uid()).first()
    if not b:return fail('Bill not found.',404)
    b.next_due_date=advance(b.next_due_date,b.frequency)
    db.session.commit();return jsonify(bill=b.to_dict(),message='Due date advanced. No money was deducted.')
