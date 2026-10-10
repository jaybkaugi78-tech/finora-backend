from datetime import datetime, date
from flask import jsonify, request
from flask_jwt_extended import get_jwt_identity
from ..models import Account,Category
from ..services.finance import amount

def uid(): return int(get_jwt_identity())
def body(): return request.get_json(silent=True) or {}
def fail(message,code=400): return jsonify(error=str(message)),code
def parse_date(value):
    try: return date.fromisoformat(str(value)[:10])
    except (ValueError,TypeError): raise ValueError('Invalid date; use YYYY-MM-DD.')
def parse_datetime(value):
    try: return datetime.fromisoformat(str(value).replace('Z','+00:00')).replace(tzinfo=None)
    except (ValueError,TypeError): raise ValueError('Invalid transaction date.')
def account_for(user_id,id):
    a=Account.query.filter_by(user_id=user_id,id=id).first()
    if not a: raise ValueError('Account not found.')
    return a
def category_for(user_id,id):
    if id is None: return None
    c=Category.query.filter_by(user_id=user_id,id=id).first()
    if not c: raise ValueError('Category not found.')
    return c
