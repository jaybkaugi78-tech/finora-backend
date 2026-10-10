from flask import Blueprint,jsonify
from flask_jwt_extended import jwt_required
from ..extensions import db
from ..models import Category
from .common import uid,body,fail
bp=Blueprint('categories',__name__)
@bp.get('/categories')
@jwt_required()
def listing():
    q=Category.query.filter_by(user_id=uid())
    from flask import request
    if request.args.get('type'): q=q.filter_by(category_type=request.args['type'])
    return jsonify(categories=[c.to_dict() for c in q.order_by(Category.name)])
@bp.post('/categories')
@jwt_required()
def create():
    d=body();name=str(d.get('name') or '').strip();typ=d.get('category_type') or d.get('type') or 'expense'
    if not name or typ not in ('income','expense'): return fail('Valid name and category type required.')
    c=Category(user_id=uid(),name=name,category_type=typ);db.session.add(c);db.session.commit();return jsonify(category=c.to_dict()),201
