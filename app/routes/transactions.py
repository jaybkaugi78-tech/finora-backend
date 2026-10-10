import hashlib,json
from flask import Blueprint,jsonify,request
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import Transaction,IdempotencyKey
from ..services.finance import amount,lock_accounts,apply
from .common import uid,body,fail,category_for,parse_datetime
bp=Blueprint('transactions',__name__)
def validate(d,user_id,existing=None):
    typ=d.get('transaction_type',existing.transaction_type if existing else None)
    if typ not in ('income','expense','transfer'): raise ValueError('Invalid transaction type.')
    n=amount(d.get('amount',existing.amount if existing else None))
    aid=int(d.get('account_id',existing.account_id if existing else 0))
    dest=d.get('destination_account_id',existing.destination_account_id if existing else None)
    dest=int(dest) if dest not in ('',None) else None
    if typ!='transfer': dest=None
    if typ=='transfer' and (dest is None or dest==aid): raise ValueError('Choose a different destination account.')
    cid=d.get('category_id',existing.category_id if existing else None)
    cid=int(cid) if cid not in ('',None) else None
    cat=category_for(user_id,cid)
    if cat and cat.category_type!=typ and typ!='transfer': raise ValueError('Category type does not match transaction type.')
    dt=parse_datetime(d['transaction_date']) if d.get('transaction_date') else (existing.transaction_date if existing else None)
    return dict(transaction_type=typ,amount=n,account_id=aid,destination_account_id=dest,category_id=cid,merchant=d.get('merchant',existing.merchant if existing else None),description=d.get('description',existing.description if existing else None),notes=d.get('notes',existing.notes if existing else None),is_recurring=bool(d.get('is_recurring',existing.is_recurring if existing else False)),**({'transaction_date':dt} if dt else {}))
@bp.get('/transactions')
@jwt_required()
def listing():
    q=Transaction.query.filter_by(user_id=uid())
    if request.args.get('type'): q=q.filter_by(transaction_type=request.args['type'])
    if request.args.get('account_id'):
        aid=int(request.args['account_id']);q=q.filter((Transaction.account_id==aid)|(Transaction.destination_account_id==aid))
    if request.args.get('category_id'): q=q.filter_by(category_id=int(request.args['category_id']))
    if request.args.get('search'):
        s=f"%{request.args['search']}%";q=q.filter((Transaction.merchant.ilike(s))|(Transaction.description.ilike(s)))
    return jsonify(transactions=[t.to_dict() for t in q.order_by(Transaction.transaction_date.desc(),Transaction.id.desc()).limit(500)])
@bp.post('/transactions')
@jwt_required()
def create():
    user=uid();d=body();key=request.headers.get('Idempotency-Key','').strip()
    if len(key)>128: return fail('Idempotency key too long.')
    payload_hash=hashlib.sha256(json.dumps(d,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    try:
        if key:
            prev=IdempotencyKey.query.filter_by(user_id=user,key=key).first()
            if prev:
                if prev.payload_hash!=payload_hash: return fail('Idempotency key reused with different data.',409)
                return jsonify(prev.response_json),200
        vals=validate(d,user)
        accounts=lock_accounts(user,[vals['account_id'],vals['destination_account_id']])
        tx=Transaction(user_id=user,**vals);db.session.add(tx);apply(tx,accounts)
        db.session.flush();result={'transaction':tx.to_dict()}
        if key: db.session.add(IdempotencyKey(user_id=user,key=key,payload_hash=payload_hash,response_json=result))
        db.session.commit();return jsonify(result),201
    except (ValueError,TypeError) as e: db.session.rollback();return fail(e)
    except IntegrityError:
        db.session.rollback()
        if key:
            prev=IdempotencyKey.query.filter_by(user_id=user,key=key).first()
            if prev and prev.payload_hash==payload_hash:return jsonify(prev.response_json),200
        return fail('Conflicting request.',409)
@bp.route('/transactions/<int:id>',methods=['GET','PATCH','PUT','DELETE'])
@jwt_required()
def item(id):
    user=uid();tx=Transaction.query.filter_by(id=id,user_id=user).first()
    if not tx:return fail('Transaction not found.',404)
    if request.method=='GET':return jsonify(transaction=tx.to_dict())
    try:
        vals=validate(body(),user,tx) if request.method!='DELETE' else None
        ids=[tx.account_id,tx.destination_account_id]
        if vals:ids.extend([vals['account_id'],vals['destination_account_id']])
        accounts=lock_accounts(user,ids)
        apply(tx,accounts,reverse=True)
        if request.method=='DELETE':db.session.delete(tx);db.session.commit();return jsonify(message='Transaction deleted.')
        for k,v in vals.items():setattr(tx,k,v)
        apply(tx,accounts)
        db.session.commit();return jsonify(transaction=tx.to_dict())
    except (ValueError,TypeError) as e:db.session.rollback();return fail(e)
