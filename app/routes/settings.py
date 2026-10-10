from flask import Blueprint,jsonify
from flask_jwt_extended import jwt_required
from ..extensions import db
from ..models import User
from .common import uid,body,fail
bp=Blueprint('settings',__name__)
@bp.get('/settings')
@jwt_required()
def show():return jsonify(user=User.query.get_or_404(uid()).to_dict())
@bp.route('/settings/profile',methods=['PATCH','PUT'])
@jwt_required()
def profile():
    u=User.query.get_or_404(uid());d=body()
    if 'full_name' in d:
        if not str(d['full_name']).strip():return fail('Name required.')
        u.full_name=d['full_name'].strip()
    if 'email' in d:
        e=str(d['email']).strip().lower()
        if '@' not in e:return fail('Invalid email.')
        if User.query.filter(User.email==e,User.id!=u.id).first():return fail('Email already used.',409)
        u.email=e
    for k in ('currency','country','timezone'):
        if k in d:setattr(u,k,str(d[k]).strip())
    db.session.commit();return jsonify(user=u.to_dict())
@bp.post('/settings/password')
@jwt_required()
def password():
    u=User.query.get_or_404(uid());d=body();old=d.get('current_password') or d.get('old_password') or '';new=d.get('new_password') or ''
    if not u.check_password(old):return fail('Current password incorrect.',403)
    if len(new)<10:return fail('New password must have at least 10 characters.')
    u.set_password(new);db.session.commit();return jsonify(message='Password updated.')
