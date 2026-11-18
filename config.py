import os
import secrets
import hashlib
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env')


def configuration():
    # Keep SQLite and secrets outside synchronized/protected Documents on Windows.
    workspace_id = hashlib.sha256(str(ROOT).encode()).hexdigest()[:10]
    default_instance = Path(os.getenv('LOCALAPPDATA', str(ROOT))) / 'MediBed' / workspace_id if os.name == 'nt' else ROOT / 'instance'
    # Separate schema, secrets and sessions from the previous fictional dataset.
    instance = Path(os.getenv('MEDIBED_INSTANCE_DIR', str(default_instance / 'pune-v2')))
    instance.mkdir(parents=True, exist_ok=True)
    # Persist a random local key across restarts without committing secrets.
    key_file = instance / '.secret_key'
    secret = os.getenv('SECRET_KEY')
    production = os.getenv('APP_ENV', 'development').lower() == 'production'
    hosts = [value.strip() for value in os.getenv('TRUSTED_HOSTS', '').split(',') if value.strip()]
    render_hostname = os.getenv('RENDER_EXTERNAL_HOSTNAME', '').strip()
    if not hosts and render_hostname:
        hosts = [render_hostname]
    if production and (not secret or len(secret) < 32 or secret.startswith('replace-')):
        raise RuntimeError('Production requires a random SECRET_KEY of at least 32 characters.')
    if production and not hosts:
        raise RuntimeError('Set TRUSTED_HOSTS to your hosting domain before production startup.')
    if not secret:
        if not key_file.exists():
            key_file.write_text(secrets.token_hex(32), encoding='utf-8')
        secret = key_file.read_text(encoding='utf-8').strip()
    database_url = os.getenv('DATABASE_URL', 'sqlite:///' + (instance / 'medibed.db').as_posix())
    if database_url.startswith('postgres://'):
        database_url = 'postgresql+psycopg://' + database_url[len('postgres://'):]
    elif database_url.startswith('postgresql://'):
        database_url = 'postgresql+psycopg://' + database_url[len('postgresql://'):]
    connect_args = {'connect_timeout': 15} if database_url.startswith('postgresql+') else {'timeout': 15}
    auto_seed = os.getenv('AUTO_SEED', 'true').strip().lower()
    if auto_seed not in ('1', 'true', 'yes', 'on', '0', 'false', 'no', 'off'):
        raise RuntimeError('AUTO_SEED must be set to true or false.')
    public_directory_seed = os.getenv('PUBLIC_DIRECTORY_SEED', 'false').strip().lower()
    if public_directory_seed not in ('1', 'true', 'yes', 'on', '0', 'false', 'no', 'off'):
        raise RuntimeError('PUBLIC_DIRECTORY_SEED must be set to true or false.')
    return {
        'SECRET_KEY': secret,
        'PRODUCTION': production,
        'INSTANCE_DIRECTORY': str(instance),
        'TRUSTED_HOSTS': hosts or None,
        'TRUST_PROXY_HEADERS': os.getenv('TRUST_PROXY_HEADERS', 'false').lower() == 'true',
        'SQLALCHEMY_DATABASE_URI': database_url,
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
        'SQLALCHEMY_ENGINE_OPTIONS': {'connect_args': connect_args},
        'SESSION_COOKIE_HTTPONLY': True,
        'SESSION_COOKIE_NAME': 'medibed_pune_session',
        'SESSION_COOKIE_SAMESITE': 'Lax',
        'SESSION_COOKIE_SECURE': production or os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true',
        'PERMANENT_SESSION_LIFETIME': timedelta(hours=2),
        'MAX_CONTENT_LENGTH': 32 * 1024,
        'AUTO_SEED': auto_seed in ('1', 'true', 'yes', 'on'),
        'PUBLIC_DIRECTORY_SEED': public_directory_seed in ('1', 'true', 'yes', 'on'),
        'RATE_LIMIT_ENABLED': True,
        'LOGIN_RATE_LIMIT': 20,
        'REGISTER_RATE_LIMIT': 5,
        'PRIVACY_CONTACT': os.getenv('PRIVACY_CONTACT', ''),
    }
