from models import db, User
from conftest import APIClient


def test_register_login_logout(app):
    c = APIClient(app)
    response = c.send('POST', '/api/auth/register', {'name': 'Test Patient', 'email': 'TEST@example.com', 'password': 'Strong@123'})
    assert response.status_code == 201
    assert response.json['data']['user']['role'] == 'patient'
    assert c.get('/api/auth/me').json['data']['user']['email'] == 'test@example.com'
    with app.app_context():
        user = db.session.scalar(db.select(User).where(User.email == 'test@example.com'))
        assert user.password_hash != 'Strong@123'
    assert c.send('POST', '/api/auth/logout').status_code == 200
    assert c.get('/api/requests/mine').status_code == 401
    assert c.send('POST', '/api/auth/login', {'email': 'test@example.com', 'password': 'Strong@123'}).status_code == 200


def test_auth_validation_and_csrf(app):
    c = APIClient(app)
    assert c.client.post('/api/auth/login', json={'email': 'a@b.com', 'password': 'pass'}).status_code == 400
    assert c.send('POST', '/api/auth/register', {'name': 'X', 'email': 'bad', 'password': '123'}).status_code == 400
    assert c.send('POST', '/api/auth/register', {'name': 'Admin', 'email': 'admin@x.com', 'password': 'Strong@123', 'role': 'hospital_admin'}).status_code == 403
    assert c.send('POST', '/api/auth/login', {'email': 'patient@medibed.demo', 'password': 'wrong'}).status_code == 401
    assert c.send('POST', '/api/auth/register', {'name': 'Duplicate', 'email': 'patient@medibed.demo', 'password': 'Strong@123'}).status_code == 409


def test_role_boundaries(app, patient, admin):
    anonymous = APIClient(app)
    assert anonymous.get('/api/admin/beds').status_code == 401
    assert patient.get('/api/admin/beds').status_code == 403
    assert patient.send('POST', '/api/admin/beds', {}).status_code == 403
    assert admin.get('/api/requests/mine').status_code == 403
    assert patient.get('/api/dashboard/stats?scope=admin').status_code == 403
