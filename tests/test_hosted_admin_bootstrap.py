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


def test_directory_only_bootstrap_preserves_patients_and_existing_passwords(tmp_path, monkeypatch):
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
        monkeypatch.setenv('HOSPITAL_ADMIN_BOOTSTRAP_JSON', json.dumps({key: 'DifferentFixture123!' for key in passwords}))
        seed_data(create_admin_accounts=False)
        assert {user.id: user.password_hash for user in admins} == before
        assert db.session.scalar(db.select(db.func.count(User.id))) == 7
        monkeypatch.delenv('HOSPITAL_ADMIN_BOOTSTRAP_JSON')
        seed_data(create_admin_accounts=False)
        assert db.session.scalar(db.select(db.func.count(User.id))) == 7


@pytest.mark.parametrize('value', ['{', '{}', '[]', json.dumps({spec['slug']: 'weak' for spec in HOSPITALS})])
def test_invalid_bootstrap_fails_before_account_creation(tmp_path, monkeypatch, value):
    monkeypatch.setenv('HOSPITAL_ADMIN_BOOTSTRAP_JSON', value)
    with pytest.raises(RuntimeError, match='bootstrap'):
        make_app(tmp_path, monkeypatch)
