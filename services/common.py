import re
from functools import wraps
from flask import abort, g, jsonify, request


def success(data=None, message=None, status=200):
    return jsonify(ok=True, data=data, message=message), status


def role_required(role=None):
    def decorate(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            if not g.user:
                abort(401, description='Please log in to continue.')
            if role and g.user.role != role:
                abort(403, description='This action is not available for your account role.')
            return fn(*args, **kwargs)
        return wrapped
    return decorate


def body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        abort(400, description='Send a JSON object.')
    return data


def choice(value, options, label):
    if value not in options:
        abort(400, description=f'{label} must be one of: {", ".join(options)}.')
    return value


def boolean(data, key, default=False):
    value = data.get(key, default)
    if type(value) is not bool:
        abort(400, description=f'{key} must be a boolean.')
    return value


def query_bool(key):
    value = request.args.get(key)
    if value is None or value == '':
        return False
    if value.lower() not in ('true', 'false', '1', '0'):
        abort(400, description=f'{key} must be true or false.')
    return value.lower() in ('true', '1')


def integer(value, label):
    if isinstance(value, bool) or not re.fullmatch(r'[1-9][0-9]*', str(value)):
        abort(400, description=f'{label} must be a positive integer.')
    return int(value)


def text(value, label, minimum=1, maximum=80):
    if not isinstance(value, str) or not minimum <= len(value.strip()) <= maximum:
        abort(400, description=f'{label} must be {minimum}–{maximum} characters.')
    if any(ord(c) < 32 for c in value.strip()):
        abort(400, description=f'{label} contains invalid characters.')
    return value.strip()
