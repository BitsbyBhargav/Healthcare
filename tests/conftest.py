import pytest
from app import create_app
from models import db
from seed import seed_data


@pytest.fixture
def app(tmp_path):
    application = create_app({'TESTING': True, 'SECRET_KEY': 'test-only-key',
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + (tmp_path / 'test.db').as_posix(), 'AUTO_SEED': False})
    with application.app_context():
        seed_data()
    yield application
    with application.app_context():
        db.session.remove()
        db.engine.dispose()


class APIClient:
    def __init__(self, app):
        self.client = app.test_client()
        self.token = self.client.get('/api/auth/me').json['data']['csrf_token']

    def get(self, url):
        return self.client.get(url)

    def send(self, method, url, data=None):
        response = self.client.open(url, method=method, json=data or {}, headers={'X-CSRF-Token': self.token})
        if response.is_json and response.json.get('data') and isinstance(response.json['data'], dict):
            self.token = response.json['data'].get('csrf_token', self.token)
        return response

    def login(self, email='patient@medibed.demo'):
        return self.send('POST', '/api/auth/login', {'email': email, 'password': 'Demo@123'})


@pytest.fixture
def patient(app):
    c = APIClient(app)
    assert c.login().status_code == 200
    return c


@pytest.fixture
def admin(app):
    c = APIClient(app)
    assert c.login('admin@medibed.demo').status_code == 200
    return c
