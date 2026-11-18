import re
import secrets
from flask import Blueprint, abort, g, session
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.exc import IntegrityError
from models import db, User
from services.common import body, success, text
from services.security import throttle

bp = Blueprint('auth', __name__, url_prefix='/api/auth')


@bp.get('/me')
def me():
    return success({'user': g.user.public() if g.user else None, 'csrf_token': session['csrf_token']})


def establish(user):
    session.clear()
    session.update(user_id=user.id, csrf_token=secrets.token_urlsafe(32))
    session.permanent = True
    return {'user': user.public(), 'csrf_token': session['csrf_token']}


@bp.post('/register')
def register():
    throttle('register')
    data = body()
    if 'role' in data and data['role'] != 'patient':
        abort(403, description='Hospital workspace accounts are provisioned privately.')
    if data.get('accept_privacy') is not True:
        abort(400, description='Please read and acknowledge the privacy notice before registering.')
    name = text(data.get('name'), 'Name', 2, 80)
    email = text(data.get('email'), 'Email', 5, 254).lower()
    password = data.get('password')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email):
        abort(400, description='Enter a valid email address.')
    if not isinstance(password, str) or not 10 <= len(password) <= 128 or not re.search(r'[A-Za-z]', password) or not re.search(r'[0-9]', password):
        abort(400, description='Use 10–128 characters including a letter and a number.')
    user = User(name=name, email=email, password_hash=generate_password_hash(password), role='patient')
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        abort(409, description='An account with this email already exists.')
    return success(establish(user), 'Your patient account is ready.', 201)


@bp.post('/login')
def login():
    throttle('login')
    data = body()
    identifier = text(data.get('identifier', data.get('email')), 'Email or hospital username', 1, 254).lower()
    password = data.get('password')
    if not isinstance(password, str) or len(password) > 128:
        abort(400, description='Enter a valid password.')
    user = db.session.scalar(db.select(User).where(db.or_(User.email == identifier, User.username == identifier)))
    if not user or not check_password_hash(user.password_hash, password):
        abort(401, description='Email, username or password is incorrect.')
    return success(establish(user), 'Welcome back.')


@bp.post('/logout')
def logout():
    session.clear()
    session['csrf_token'] = secrets.token_urlsafe(32)
    return success({'csrf_token': session['csrf_token']}, 'You have signed out.')
