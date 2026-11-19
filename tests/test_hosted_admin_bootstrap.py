import json

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

from app import create_app
from data.pune_hospitals import HOSPITALS
from models import db, User
from seed import seed_data


def make_app(tmp_path, monkeypatch):
    monkeypatch.setenv('MEDIBED_INSTANCE_DIR', str(tmp_path / 'runtime'))
    return create_app({'TESTING': True, 'AUTO_SEED': False,
        'PUBLIC_DIRECTORY_SEED': True, 'RATE_LIMIT_ENABLED': False,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + (tmp_path / 'bootstrap.db').as_posix()})


def test_directory_only_bootstrap_preserves_patients_and_syncs_explicit_passwords(tmp_path, monkeypatch):
    monkeypatch.delenv('HOSPITAL_ADMIN_BOOTSTRAP_JSON', raising=False)
    app = make_app(tmp_path, monkeypatch)
    with app.app_context():
        assert db.session.scalar(db.select(db.func.count(User.id))) == 0
        patient = User(name='Existing patient', email='existing@example.com', role='patient',
            password_hash=generate_password_hash('PatientPassword123'))
        db.session.add(patient)
        db.session.commit()
        patient_id = patient.id
        passwords = {spec['slug']: 'PrivateFixturePassword123!' for spec in HOSPITALS}
        monkeypatch.setenv('HOSPITAL_ADMIN_BOOTSTRAP_JSON', json.dumps(passwords))
        seed_data(create_admin_accounts=False)
        admins = db.session.scalars(db.select(User).where(User.role == 'hospital_admin')).all()
        assert {user.username for user in admins} == set(passwords)
        assert all(user.hospital.slug == user.username for user in admins)
        assert all(check_password_hash(user.password_hash, passwords[user.username]) for user in admins)
        assert db.session.get(User, patient_id).email == 'existing@example.com'
        before = {user.id: user.password_hash for user in admins}
        seed_data(create_admin_accounts=False)
        assert {user.id: user.password_hash for user in admins} == before
        monkeypatch.setenv('HOSPITAL_ADMIN_BOOTSTRAP_JSON', json.dumps({key: 'DifferentFixture123!' for key in passwords}))
        seed_data(create_admin_accounts=False)
        assert all(check_password_hash(user.password_hash, 'DifferentFixture123!') for user in admins)
        after = {user.id: user.password_hash for user in admins}
        assert db.session.scalar(db.select(db.func.count(User.id))) == 7
        monkeypatch.delenv('HOSPITAL_ADMIN_BOOTSTRAP_JSON')
        seed_data(create_admin_accounts=False)
        assert {user.id: user.password_hash for user in admins} == after
        assert db.session.scalar(db.select(db.func.count(User.id))) == 7


@pytest.mark.parametrize('value', ['{', '{}', '[]', json.dumps({spec['slug']: 'weak' for spec in HOSPITALS})])
def test_invalid_bootstrap_fails_before_account_creation(tmp_path, monkeypatch, value):
    monkeypatch.setenv('HOSPITAL_ADMIN_BOOTSTRAP_JSON', value)
    with pytest.raises(RuntimeError, match='bootstrap'):
        make_app(tmp_path, monkeypatch)


def test_bootstrapped_admins_can_decide_only_their_hospital_requests(tmp_path, monkeypatch):
    password = 'PrivateFixturePassword123!'
    monkeypatch.setenv('HOSPITAL_ADMIN_BOOTSTRAP_JSON', json.dumps({spec['slug']: password for spec in HOSPITALS}))
    app = make_app(tmp_path, monkeypatch)

    def client():
        value = app.test_client()
        value.csrf = value.get('/api/auth/me').json['data']['csrf_token']
        return value

    def post(value, path, payload):
        result = value.post(path, json=payload, headers={'X-CSRF-Token': value.csrf})
        if result.is_json and isinstance(result.json.get('data'), dict):
            value.csrf = result.json['data'].get('csrf_token', value.csrf)
        return result

    patient = client()
    assert post(patient, '/api/auth/register', {'name': 'Workflow test patient', 'email': 'workflow@example.com',
        'password': 'PatientFixture123!', 'accept_privacy': True}).status_code == 201
    first = post(patient, '/api/requests', {'hospital_id': 1, 'requested_bed_type': 'general', 'acknowledge_unverified': True})
    second = post(patient, '/api/requests', {'hospital_id': 2, 'requested_bed_type': 'general', 'acknowledge_unverified': True})
    assert first.status_code == second.status_code == 201
    first_id, second_id = first.json['data']['id'], second.json['data']['id']
    jehangir, ruby = client(), client()
    for value, username in ((jehangir, 'jehangir'), (ruby, 'ruby-hall')):
        assert post(value, '/api/auth/login', {'identifier': username, 'password': password}).status_code == 200
        assert value.get('/admin').status_code == 200
    assert {r['id'] for r in jehangir.get('/api/admin/requests').json['data']['requests']} == {first_id}
    assert post(jehangir, f'/api/admin/requests/{second_id}/decision', {'decision': 'reject'}).status_code == 403
    assert post(jehangir, f'/api/admin/requests/{first_id}/decision', {'decision': 'approve'}).json['data']['status'] == 'approved'
    assert post(ruby, f'/api/admin/requests/{second_id}/decision', {'decision': 'reject'}).json['data']['status'] == 'rejected'
    assert {r['id']: r['status'] for r in patient.get('/api/requests/mine').json['data']['requests']} == {first_id: 'approved', second_id: 'rejected'}
