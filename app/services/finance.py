from datetime import datetime
from decimal import Decimal, InvalidOperation
from sqlalchemy import func
from ..extensions import db
from ..models import Account, Transaction

CENT=Decimal('0.01')
def amount(value, allow_zero=False):
    if isinstance(value,bool) or value is None: raise ValueError('A valid amount is required.')
    try: d=Decimal(str(value))
    except (InvalidOperation,ValueError): raise ValueError('Invalid amount.')
    if not d.is_finite() or d.as_tuple().exponent < -2 or (d < 0 if allow_zero else d <= 0) or d > Decimal('999999999999.99'):
        raise ValueError('Amount must be positive, have at most 2 decimals and fit the account limit.')
    return d.quantize(CENT)

def lock_accounts(user_id, ids):
    ids=sorted(set(int(i) for i in ids if i is not None))
    rows=Account.query.filter(Account.user_id==user_id,Account.id.in_(ids)).order_by(Account.id).with_for_update().all()
    if len(rows)!=len(ids): raise ValueError('Account not found.')
    return {a.id:a for a in rows}

def apply(tx, accounts, reverse=False):
    sign=Decimal('-1') if reverse else Decimal('1')
    a=accounts[tx.account_id]
    if a.is_archived: raise ValueError('Archived accounts cannot be used for transactions.')
    n=amount(tx.amount)*sign
    if tx.transaction_type=='income': a.balance+=n
    elif tx.transaction_type=='expense': a.balance-=n
    elif tx.transaction_type=='transfer':
        if not tx.destination_account_id or tx.destination_account_id==tx.account_id: raise ValueError('Choose a different destination account.')
        dest=accounts[tx.destination_account_id]
        if dest.is_archived: raise ValueError('Archived accounts cannot be used for transfers.')
        if a.currency!=dest.currency: raise ValueError('Cross-currency transfers require conversion support.')
        a.balance-=n
        dest.balance+=n
    else: raise ValueError('Invalid transaction type.')

def month_bounds(year,month):
    start=datetime(year,month,1)
    end=datetime(year+1,1,1) if month==12 else datetime(year,month+1,1)
    return start,end

def totals(user_id,year,month):
    start,end=month_bounds(year,month)
    rows=db.session.query(Transaction.transaction_type,func.coalesce(func.sum(Transaction.amount),0)).filter(Transaction.user_id==user_id,Transaction.transaction_date>=start,Transaction.transaction_date<end).group_by(Transaction.transaction_type).all()
    d={t:float(v) for t,v in rows}
    return d.get('income',0),d.get('expense',0)

def reconcile(user_id):
    result=[]
    for a in Account.query.filter_by(user_id=user_id).order_by(Account.id):
        expected=Decimal(a.opening_balance)
        for t in Transaction.query.filter_by(user_id=user_id):
            n=Decimal(t.amount)
            if t.account_id==a.id:
                if t.transaction_type=='income': expected+=n
                elif t.transaction_type in ('expense','transfer'): expected-=n
            if t.transaction_type=='transfer' and t.destination_account_id==a.id: expected+=n
        result.append(dict(account_id=a.id,name=a.name,currency=a.currency,stored_balance=float(a.balance),expected_balance=float(expected),difference=float(Decimal(a.balance)-expected),matches=Decimal(a.balance)==expected))
    return result
