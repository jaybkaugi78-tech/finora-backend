from app.services.finance import amount
import pytest

def test_amount():
    assert str(amount('100.50'))=='100.50'
    for bad in ('1.001','-2','NaN',None,'0'):
        with pytest.raises(ValueError):amount(bad)

def test_expense_edit_delete(client,auth):
    r=client.post('/api/accounts',headers=auth,json={'name':'Cash','account_type':'cash','balance':'10000.00'});assert r.status_code==201,r.json
    aid=r.json['account']['id']
    r=client.post('/api/transactions',headers=auth,json={'account_id':aid,'transaction_type':'expense','amount':'500.00'});assert r.status_code==201,r.json
    tid=r.json['transaction']['id']
    assert client.get('/api/accounts',headers=auth).json['accounts'][0]['balance']==9500
    r=client.patch(f'/api/transactions/{tid}',headers=auth,json={'amount':'800.00'});assert r.status_code==200,r.json
    assert client.get('/api/accounts',headers=auth).json['accounts'][0]['balance']==9200
    r=client.delete(f'/api/transactions/{tid}',headers=auth);assert r.status_code==200,r.json
    assert client.get('/api/accounts',headers=auth).json['accounts'][0]['balance']==10000
    assert client.get('/api/analytics/reconcile',headers=auth).json['all_match'] is True

def test_transfer_and_idempotency(client,auth):
    a=client.post('/api/accounts',headers=auth,json={'name':'A','balance':'1000'}).json['account']['id']
    b=client.post('/api/accounts',headers=auth,json={'name':'B','balance':'500'}).json['account']['id']
    payload={'account_id':a,'destination_account_id':b,'transaction_type':'transfer','amount':'200'}
    h={**auth,'Idempotency-Key':'example-request-1'}
    assert client.post('/api/transactions',headers=h,json=payload).status_code==201
    assert client.post('/api/transactions',headers=h,json=payload).status_code==200
    balances={x['id']:x['balance'] for x in client.get('/api/accounts',headers=auth).json['accounts']}
    assert balances[a]==800 and balances[b]==700
    assert client.get('/api/analytics/reconcile',headers=auth).json['all_match'] is True

def test_invalid_edit_does_not_change_balance(client,auth):
    a=client.post('/api/accounts',headers=auth,json={'name':'Cash','balance':'100'}).json['account']['id']
    t=client.post('/api/transactions',headers=auth,json={'account_id':a,'transaction_type':'expense','amount':'10'}).json['transaction']['id']
    assert client.patch(f'/api/transactions/{t}',headers=auth,json={'amount':'NaN'}).status_code==400
    assert client.get('/api/accounts',headers=auth).json['accounts'][0]['balance']==90


def test_cross_currency_transfer_rejected(client,auth):
    a=client.post('/api/accounts',headers=auth,json={'name':'KES','balance':'1000','currency':'KES'}).json['account']['id']
    b=client.post('/api/accounts',headers=auth,json={'name':'USD','balance':'10','currency':'USD'}).json['account']['id']
    r=client.post('/api/transactions',headers=auth,json={'account_id':a,'destination_account_id':b,'transaction_type':'transfer','amount':'100'})
    assert r.status_code==400
    balances={x['id']:x['balance'] for x in client.get('/api/accounts',headers=auth).json['accounts']}
    assert balances[a]==1000 and balances[b]==10
    assert client.get('/api/analytics/dashboard',headers=auth).json['mixed_currencies'] is True
