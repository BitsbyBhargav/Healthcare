import sys
# Avoid source bytecode writes in synchronized/protected project folders.
sys.dont_write_bytecode = True

import hmac
import os
import secrets
from urllib.parse import urlsplit
from flask import Flask, abort, g, jsonify, render_template, request, session, redirect
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError
from config import configuration
from models import db, User


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.update(configuration())
    if test_config:
        app.config.update(test_config)
    if app.config['TRUST_PROXY_HEADERS']:
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    db.init_app(app)

    @app.before_request
    def security():
        if app.config['PRODUCTION'] and not request.is_secure:
            return redirect(request.url.replace('http://', 'https://', 1), code=308)
        session.setdefault('csrf_token', secrets.token_urlsafe(32))
        g.user = db.session.get(User, session['user_id']) if session.get('user_id') else None
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            origin = request.headers.get('Origin')
            if origin and (urlsplit(origin).netloc.lower() != request.host.lower() or urlsplit(origin).scheme != request.scheme):
                abort(400, description='Cross-origin write requests are not allowed.')
            supplied = request.headers.get('X-CSRF-Token', '')
            expected = session.get('csrf_token', '')
            if not supplied or not hmac.compare_digest(supplied.encode('utf-8'), expected.encode('utf-8')):
                abort(400, description='CSRF token missing or expired. Refresh this page and try again.')

    @app.context_processor
    def context():
        return {'current_user': g.get('user'), 'csrf_token': session.get('csrf_token', ''), 'privacy_contact': app.config['PRIVACY_CONTACT']}

    @app.after_request
    def headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if app.config['PRODUCTION'] and request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=86400'
        if request.path.startswith('/api/') or response.mimetype == 'text/html':
            response.headers['Cache-Control'] = 'no-store'
        return response

    @app.errorhandler(HTTPException)
    def http_error(error):
        db.session.rollback()
        if request.path.startswith('/api/'):
            response = jsonify(ok=False, data=None, error={'code': error.code, 'message': error.description})
            response.status_code = error.code
            if error.code == 429:
                response.headers['Retry-After'] = '900'
            return response
        return render_template('error.html', code=error.code, message=error.description), error.code

    @app.errorhandler(Exception)
    def unexpected(error):
        db.session.rollback()
        app.logger.exception('Unexpected application error')
        if request.path.startswith('/api/'):
            return jsonify(ok=False, data=None, error={'code': 500, 'message': 'Something went wrong. Please try again.'}), 500
        return render_template('error.html', code=500, message='Something went wrong. Please try again.'), 500

    from routes import auth, public, patient, admin, predictions
    for blueprint in (auth.bp, public.bp, patient.bp, admin.bp, predictions.bp):
        app.register_blueprint(blueprint)
    with app.app_context():
        db.create_all()
        if app.config['AUTO_SEED']:
            from seed import seed_data
            seed_data()
    return app


if __name__ == '__main__':
    create_app().run(host='127.0.0.1', port=int(os.getenv('PORT', '5000')), debug=False)
