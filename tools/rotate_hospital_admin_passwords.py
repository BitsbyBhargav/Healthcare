"""Securely set fresh passwords for all hospital admin accounts."""
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True

from sqlalchemy.engine import make_url
from werkzeug.security import generate_password_hash
from app import create_app
from models import db, User


def rotate_passwords():
    database_url = os.getenv('DATABASE_URL')
    if database_url and make_url(database_url).get_backend_name() != 'sqlite':
        raise RuntimeError('Unset DATABASE_URL before rotating local SQLite passwords.')
    app = create_app({'AUTO_SEED': False})
    with app.app_context():
        if db.engine.dialect.name != 'sqlite':
            raise RuntimeError('This utility only rotates passwords in the local SQLite database.')
        admins = db.session.scalars(
            db.select(User).where(User.role == 'hospital_admin').order_by(User.username)
        ).all()
        if not admins:
            raise RuntimeError('No hospital admin accounts were found.')

        updates = []
        used_passwords = set()
        for admin in admins:
            username = admin.username or admin.email
            while True:
                password = getpass.getpass(f'New password for {username}: ')
                confirmation = getpass.getpass(f'Confirm password for {username}: ')
                if password != confirmation:
                    print('Passwords do not match; try again.')
                elif len(password) < 14:
                    print('Use a password with at least 14 characters.')
                elif password in used_passwords:
                    print('Use a different password for each account.')
                else:
                    used_passwords.add(password)
                    updates.append((admin, generate_password_hash(password)))
                    break

        try:
            for admin, password_hash in updates:
                admin.password_hash = password_hash
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
        print(f'Updated passwords for {len(updates)} hospital admin accounts.')


if __name__ == '__main__':
    rotate_passwords()
