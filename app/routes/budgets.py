from datetime import date
from flask import Blueprint,jsonify,request
from flask_jwt_extended import jwt_required
from sqlalchemy import func
from ..extensions import db
from ..models import Budget,Transaction
from ..services.finance import amount,month_bounds
from .common import uid,body,fail,category_for
bp=Blueprint('budgets',__name__)
def serialize(b):
    start,end=month_bounds(b.year,b.month)
    spent=db.session.query(func.coalesce(func.sum(Transaction.amount),0)).filter(Transaction.user_id==b.user_id,Transaction.transaction_type=='expense',Transaction.category_id==b.category_id,Transaction.transaction_date>=start,Transaction.transaction_date<end).scalar()
    s=float(spent or 0);v=float(b.amount);p=round(s/v*100,1) if v else 0
    return dict(id=b.id,category_id=b.category_id,category=b.category.to_dict(),amount=v,month=b.month,year=b.year,spent=s,remaining=v-s,percentage=p,is_over_budget=s>v)
@bp.get('/budgets')
@jwt_required()
def listing():
    now=date.today();year=int(request.args.get('year',now.year));month=int(request.args.get('month',now.month))
    if not 1<=month<=12:return fail('Invalid month.')
    return jsonify(budgets=[serialize(b) for b in Budget.query.filter_by(user_id=uid(),month=month,year=year).all()])
@bp.post('/budgets')
@jwt_required()
def create():
    d=body()
    try:
        cid=int(d['category_id']);cat=category_for(uid(),cid)
        if cat.category_type!='expense':raise ValueError('Budgets require an expense category.')
        m=int(d.get('month',date.today().month));y=int(d.get('year',date.today().year))
        if not 1<=m<=12:raise ValueError('Invalid month.')
        b=Budget(user_id=uid(),category_id=cid,amount=amount(d.get('amount')),month=m,year=y)
        db.session.add(b);db.session.commit();return jsonify(budget=serialize(b)),201
    except (ValueError,TypeError,KeyError) as e:db.session.rollback();return fail(e)
@bp.route('/budgets/<int:id>',methods=['PATCH','PUT','DELETE'])
@jwt_required()
def item(id):
    b=Budget.query.filter_by(id=id,user_id=uid()).first()
    if not b:return fail('Budget not found.',404)
    try:
        if request.method=='DELETE':db.session.delete(b);db.session.commit();return jsonify(message='Budget deleted.')
        d=body()
        if 'amount' in d:b.amount=amount(d['amount'])
        db.session.commit();return jsonify(budget=serialize(b))
    except (ValueError,TypeError) as e:db.session.rollback();return fail(e)
