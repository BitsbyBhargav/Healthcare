"""SQLite-backed fixed-window throttle, shared by WSGI workers."""
import hashlib
import hmac
import time
from flask import current_app, request, abort, g
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from models import db, RateBucket, AuditEvent


def throttle(kind):
    if not current_app.config['RATE_LIMIT_ENABLED']:
        return
    seconds = 300 if kind == 'login' else 900
    limit = current_app.config['LOGIN_RATE_LIMIT' if kind == 'login' else 'REGISTER_RATE_LIMIT']
    raw = f'{kind}:{request.remote_addr or "unknown"}'.encode()
    key = hmac.new(current_app.secret_key.encode(), raw, hashlib.sha256).hexdigest()
    window = int(time.time()) // seconds * seconds
    dialect = db.session.get_bind().dialect.name
    if dialect == 'sqlite':
        insert = sqlite_insert
    elif dialect == 'postgresql':
        insert = postgresql_insert
    else:
        raise RuntimeError(f'Unsupported database for rate limiting: {dialect}')
    statement = insert(RateBucket).values(key=key, window=window, attempts=1)
    statement = statement.on_conflict_do_update(index_elements=['key', 'window'], set_={'attempts': RateBucket.attempts + 1}).returning(RateBucket.attempts)
    attempts = db.session.scalar(statement)
    db.session.execute(db.delete(RateBucket).where(RateBucket.window < int(time.time()) - 86400))
    db.session.commit()
    if attempts > limit:
        abort(429, description=f'Too many {kind} attempts. Please wait {seconds // 60} minutes and try again.')


def audit(action, hospital_id=None, record_id=None):
    db.session.add(AuditEvent(actor_id=g.user.id if g.get('user') else None, hospital_id=hospital_id, action=action, record_id=record_id))
