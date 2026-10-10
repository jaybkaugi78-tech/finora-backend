from flask import Blueprint,jsonify,request
from flask_jwt_extended import jwt_required
from ..extensions import db
from ..models import Goal,GoalContribution
from ..services.finance import amount
from .common import uid,body,fail,parse_date
bp=Blueprint('goals',__name__)
@bp.get('/goals')
@jwt_required()
def listing():return jsonify(goals=[g.to_dict() for g in Goal.query.filter_by(user_id=uid()).order_by(Goal.created_at.desc())])
@bp.post('/goals')
@jwt_required()
def create():
    d=body()
    try:
        if not str(d.get('name','')).strip():raise ValueError('Goal name required.')
        g=Goal(user_id=uid(),name=d['name'].strip(),target_amount=amount(d.get('target_amount')),target_date=parse_date(d['target_date']) if d.get('target_date') else None,notes=d.get('notes'))
        db.session.add(g);db.session.commit();return jsonify(goal=g.to_dict()),201
    except (ValueError,TypeError) as e:db.session.rollback();return fail(e)
@bp.route('/goals/<int:id>',methods=['GET','PATCH','PUT','DELETE'])
@jwt_required()
def item(id):
    g=Goal.query.filter_by(id=id,user_id=uid()).first()
    if not g:return fail('Goal not found.',404)
    if request.method=='GET':return jsonify(goal=g.to_dict())
    try:
        if request.method=='DELETE':db.session.delete(g);db.session.commit();return jsonify(message='Goal deleted.')
        d=body()
        if 'name' in d:g.name=str(d['name']).strip()
        if 'target_amount' in d:g.target_amount=amount(d['target_amount'])
        if 'target_date' in d:g.target_date=parse_date(d['target_date']) if d['target_date'] else None
        if 'notes' in d:g.notes=d['notes']
        if 'is_completed' in d:g.is_completed=bool(d['is_completed'])
        db.session.commit();return jsonify(goal=g.to_dict())
    except (ValueError,TypeError) as e:db.session.rollback();return fail(e)
@bp.route('/goals/<int:id>/contributions',methods=['GET','POST'])
@jwt_required()
def contributions(id):
    g=Goal.query.filter_by(id=id,user_id=uid()).first()
    if not g:return fail('Goal not found.',404)
    if request.method=='GET':return jsonify(contributions=[c.to_dict() for c in g.contributions])
    try:
        d=body();c=GoalContribution(goal_id=id,amount=amount(d.get('amount')),note=d.get('note'));db.session.add(c);db.session.flush()
        db.session.refresh(g)
        g.is_completed=sum(x.amount for x in g.contributions)>=g.target_amount
        db.session.commit();return jsonify(contribution=c.to_dict(),goal=g.to_dict()),201
    except (ValueError,TypeError) as e:db.session.rollback();return fail(e)
@bp.delete('/goals/<int:id>/contributions/<int:cid>')
@jwt_required()
def delete_contribution(id,cid):
    g=Goal.query.filter_by(id=id,user_id=uid()).first()
    if not g:return fail('Goal not found.',404)
    c=GoalContribution.query.filter_by(id=cid,goal_id=id).first()
    if not c:return fail('Contribution not found.',404)
    db.session.delete(c);db.session.flush();db.session.expire(g,['contributions'])
    g.is_completed=sum(x.amount for x in g.contributions)>=g.target_amount
    db.session.commit();return jsonify(goal=g.to_dict())
