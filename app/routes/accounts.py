from flask import Blueprint,jsonify
from flask_jwt_extended import jwt_required
from ..extensions import db
from ..models import Account,Transaction
from ..services.finance import amount
from .common import uid,body,fail,account_for
bp=Blueprint('accounts',__name__)
@bp.get('/accounts')
@jwt_required()
def listing(): return jsonify(accounts=[a.to_dict() for a in Account.query.filter_by(user_id=uid()).order_by(Account.created_at.desc())])
@bp.post('/accounts')
@jwt_required()
def create():
    d=body()
    try:
        name=str(d.get('name') or '').strip();typ=str(d.get('account_type') or 'cash').strip()
        if not name: raise ValueError('Account name required.')
        bal=amount(d.get('balance',0),allow_zero=True); currency=str(d.get('currency') or 'KES').upper()
        if len(currency)!=3 or not currency.isalpha(): raise ValueError('Use a 3-letter currency code.')
        a=Account(user_id=uid(),name=name,account_type=typ,institution=d.get('institution'),opening_balance=bal,balance=bal,currency=currency,is_default=bool(d.get('is_default',False)))
        if a.is_default:
            Account.query.filter_by(user_id=uid(),is_default=True).update({'is_default':False})
        db.session.add(a);db.session.commit();return jsonify(account=a.to_dict()),201
    except (ValueError,TypeError) as e: db.session.rollback();return fail(e)
@bp.route('/accounts/<int:id>',methods=['GET','PATCH','PUT','DELETE'])
@jwt_required()
def item(id):
    try:
        a=account_for(uid(),id)
        if __import__('flask').request.method=='GET': return jsonify(account=a.to_dict())
        if __import__('flask').request.method=='DELETE': a.is_archived=True
        else:
            d=body()
            if 'balance' in d or 'opening_balance' in d: raise ValueError('Balances are transaction-managed and cannot be edited here.')
            for k in ('name','account_type','institution'):
                if k in d: setattr(a,k,str(d[k]).strip() if d[k] is not None else None)
            if 'currency' in d and d['currency']!=a.currency:
                if a.opening_balance != 0 or a.balance != 0 or Transaction.query.filter((Transaction.account_id==id)|(Transaction.destination_account_id==id)).first(): raise ValueError('Cannot change currency on a funded account or one with transactions.')
                a.currency=str(d['currency']).upper()
            if 'is_archived' in d: a.is_archived=bool(d['is_archived'])
            if d.get('is_default'):
                Account.query.filter_by(user_id=uid(),is_default=True).update({'is_default':False})
                a.is_default=True
            elif 'is_default' in d: a.is_default=False
        db.session.commit();return jsonify(account=a.to_dict())
    except (ValueError,TypeError) as e: db.session.rollback();return fail(e)
