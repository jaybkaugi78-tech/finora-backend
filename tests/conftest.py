import pytest
from app import create_app
from app.extensions import db
@pytest.fixture
def client():
    app=create_app({'TESTING':True,'SQLALCHEMY_DATABASE_URI':'sqlite://','JWT_SECRET_KEY':'test-key-only-for-test-suite-123456789'})
    with app.app_context():
        db.create_all()
        with app.test_client() as client: yield client
        db.session.remove();db.drop_all()
@pytest.fixture
def auth(client):
    res=client.post('/api/auth/register',json={'full_name':'Test User','email':'test@example.com','password':'testingpass123'}).json
    return {'Authorization':'Bearer '+res['token']}
