import pytest

from config import configuration


def test_postgres_render_config_uses_psycopg_and_respects_seed_flag(monkeypatch, tmp_path):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://medibed:secret@db.example/medibed')
    monkeypatch.setenv('AUTO_SEED', 'false')
    monkeypatch.setenv('PUBLIC_DIRECTORY_SEED', 'false')
    monkeypatch.setenv('MEDIBED_INSTANCE_DIR', str(tmp_path))

    config = configuration()

    assert config['SQLALCHEMY_DATABASE_URI'] == 'postgresql+psycopg://medibed:secret@db.example/medibed'
    assert config['SQLALCHEMY_ENGINE_OPTIONS']['connect_args'] == {'connect_timeout': 15}
    assert config['AUTO_SEED'] is False
    assert config['PUBLIC_DIRECTORY_SEED'] is False


def test_render_hostname_is_trusted_in_production(monkeypatch, tmp_path):
    monkeypatch.setenv('APP_ENV', 'production')
    monkeypatch.setenv('SECRET_KEY', 's' * 40)
    monkeypatch.setenv('RENDER_EXTERNAL_HOSTNAME', 'medibed-demo.onrender.com')
    monkeypatch.delenv('TRUSTED_HOSTS', raising=False)
    monkeypatch.setenv('MEDIBED_INSTANCE_DIR', str(tmp_path))

    assert configuration()['TRUSTED_HOSTS'] == ['medibed-demo.onrender.com']


def test_invalid_auto_seed_setting_fails_explicitly(monkeypatch, tmp_path):
    monkeypatch.setenv('AUTO_SEED', 'sometimes')
    monkeypatch.setenv('MEDIBED_INSTANCE_DIR', str(tmp_path))

    with pytest.raises(RuntimeError, match='AUTO_SEED'):
        configuration()


def test_invalid_public_directory_seed_setting_fails_explicitly(monkeypatch, tmp_path):
    monkeypatch.setenv('PUBLIC_DIRECTORY_SEED', 'sometimes')
    monkeypatch.setenv('MEDIBED_INSTANCE_DIR', str(tmp_path))

    with pytest.raises(RuntimeError, match='PUBLIC_DIRECTORY_SEED'):
        configuration()
