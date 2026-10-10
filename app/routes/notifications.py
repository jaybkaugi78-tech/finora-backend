from datetime import date,timedelta
from flask import Blueprint,jsonify,request
from flask_jwt_extended import jwt_required
from ..extensions import db
from ..models import Notification,Bill
from .common import uid,fail
bp=Blueprint('notifications',__name__)
def reminders(user):
    today=date.today()
    for b in Bill.query.filter_by(user_id=user,is_active=True):
        if b.next_due_date<=today+timedelta(days=b.reminder_days):
            key=f'bill:{b.id}:{b.next_due_date.isoformat()}'
            if not Notification.query.filter_by(user_id=user,dedupe_key=key).first():
                db.session.add(Notification(user_id=user,title=f'Bill reminder: {b.name}',message=f'{b.name} is due on {b.next_due_date.isoformat()}.',notification_type='bill',dedupe_key=key))
    db.session.commit()
@bp.get('/notifications')
@jwt_required()
def listing():
    reminders(uid())
    items=Notification.query.filter_by(user_id=uid()).order_by(Notification.created_at.desc()).limit(100).all()
    return jsonify(notifications=[n.to_dict() for n in items],unread_count=Notification.query.filter_by(user_id=uid(),is_read=False).count())
@bp.post('/notifications/read-all')
@jwt_required()
def all_read():
    Notification.query.filter_by(user_id=uid(),is_read=False).update({'is_read':True});db.session.commit();return jsonify(message='All marked read.')
@bp.delete('/notifications/clear-read')
@jwt_required()
def clear():
    Notification.query.filter_by(user_id=uid(),is_read=True).delete();db.session.commit();return jsonify(message='Read notifications cleared.')
@bp.route('/notifications/<int:id>',methods=['PATCH','PUT','DELETE'])
@jwt_required()
def item(id):
    n=Notification.query.filter_by(user_id=uid(),id=id).first()
    if not n:return fail('Notification not found.',404)
    if request.method=='DELETE':db.session.delete(n);db.session.commit();return jsonify(message='Deleted.')
    n.is_read=bool((request.get_json(silent=True) or {}).get('is_read',True));db.session.commit();return jsonify(notification=n.to_dict())
