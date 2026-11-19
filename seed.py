"""Seed the Pune directory and a clearly labeled Kaggle-derived demo inventory."""
import sys
sys.dont_write_bytecode = True

import csv
import json
import math
import os
import secrets
from datetime import timedelta
from pathlib import Path
from flask import current_app
from werkzeug.security import generate_password_hash
from models import db, User, Hospital, Bed, BedHistory, Ambulance, Notification, now
from data.pune_hospitals import HOSPITALS, CHECKED_AT

KAGGLE_DATA = Path(__file__).resolve().parent / 'data' / 'Hospital_Bed_Capacity_New.csv'
SYNTHETIC_BED_PREFIX = 'KAG-'
SYNTHETIC_HISTORY_DAYS = 45
DEMO_SCALE = 10
GENERAL_DEPARTMENTS = {
    'jehangir': 'Internal Medicine',
    'ruby-hall': 'Cardiology',
    'kem-pune': 'Trauma Center',
    'deenanath-mangeshkar': 'Pediatrics General',
    'poona-hospital': 'Orthopedic Surgery',
    'sassoon-general': 'Neurosurgery',
}
BED_CODES = {'general': 'GEN', 'icu': 'ICU', 'emergency': 'EMR'}


def _read_kaggle_departments():
    with KAGGLE_DATA.open(newline='', encoding='utf-8-sig') as source:
        rows = list(csv.DictReader(source))
    if not rows or 'Department' not in rows[0]:
        raise ValueError(f'Kaggle bed sample is missing or invalid: {KAGGLE_DATA}')
    departments = {row['Department']: row for row in rows}
    if len(departments) != len(rows):
        raise ValueError(f'Kaggle bed sample contains duplicate departments: {KAGGLE_DATA}')
    return departments


def _scaled_counts(row, bed_type):
    if bed_type == 'general':
        fields = ('Total_Beds', 'Free_Beds', 'Occupied_Beds')
    elif bed_type == 'icu':
        fields = ('Total_ICU_Beds', 'Free_ICU_Beds', 'Occupied_ICU_Beds')
    else:
        raise ValueError(f'Unsupported synthetic bed category: {bed_type}')

    try:
        total, available, occupied = (int(row[field]) for field in fields)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f'Invalid Kaggle bed sample values for {row.get("Department", "unknown")}') from error
    if min(total, available, occupied) < 0 or available > total or occupied > total:
        raise ValueError(f'Out-of-range Kaggle bed sample values for {row["Department"]}')

    capacity = max(1, round(total / DEMO_SCALE))
    available = min(capacity, round(available / DEMO_SCALE))
    occupied = min(capacity - available, round(occupied / DEMO_SCALE))
    return capacity, available, occupied


def seed_synthetic_inventory():
    departments = _read_kaggle_departments()
    required_departments = set(GENERAL_DEPARTMENTS.values()) | {'Emergency Department (ED)'}
    missing = required_departments - departments.keys()
    if missing:
        raise ValueError(f'Kaggle bed sample is missing departments: {", ".join(sorted(missing))}')

    today = now().date()
    for hospital in db.session.scalars(db.select(Hospital).order_by(Hospital.id)):
        if db.session.scalar(db.select(Bed.id).where(Bed.hospital_id == hospital.id).limit(1)):
            continue
        if db.session.scalar(db.select(BedHistory.id).where(BedHistory.hospital_id == hospital.id).limit(1)):
            continue
        if hospital.slug not in GENERAL_DEPARTMENTS:
            raise ValueError(f'No synthetic Kaggle profile configured for hospital {hospital.slug}')

        profile = departments[GENERAL_DEPARTMENTS[hospital.slug]]
        emergency_profile = departments['Emergency Department (ED)']
        category_data = (
            ('general', profile, 'general'),
            ('icu', profile, 'icu'),
            ('emergency', emergency_profile, 'general'),
        )
        for kind_index, (bed_type, source_row, source_type) in enumerate(category_data):
            capacity, available, occupied = _scaled_counts(source_row, source_type)
            for index in range(capacity):
                if index < available:
                    status = 'available'
                elif index < available + occupied:
                    status = 'occupied'
                else:
                    status = 'maintenance'
                is_icu = bed_type == 'icu'
                db.session.add(Bed(
                    hospital_id=hospital.id,
                    bed_code=f'{SYNTHETIC_BED_PREFIX}{hospital.id:02d}-{BED_CODES[bed_type]}-{index + 1:03d}',
                    bed_type=bed_type,
                    has_oxygen=is_icu,
                    has_ventilator=is_icu and index % 4 == 0,
                    status=status,
                ))

            swing = max(1, round(capacity * 0.14))
            for day_index in range(SYNTHETIC_HISTORY_DAYS):
                phase = day_index + hospital.id * 7 + kind_index * 11
                variation = round(swing * math.sin(phase * 0.53) + max(1, swing // 2) * math.sin(phase * 0.19))
                historical_available = available if day_index == SYNTHETIC_HISTORY_DAYS - 1 else max(0, min(capacity, available + variation))
                db.session.add(BedHistory(
                    hospital_id=hospital.id,
                    bed_type=bed_type,
                    recorded_date=today - timedelta(days=SYNTHETIC_HISTORY_DAYS - day_index - 1),
                    total_beds=capacity,
                    available_beds=historical_available,
                    source='synthetic_kaggle',
                ))


def seed_data(create_admin_accounts=True):
    # A public-directory deployment can explicitly provision its missing
    # workspace accounts without enabling unrestricted startup seeding.
    # Passwords are supplied privately by the host, never committed to Git.
    raw_bootstrap = os.getenv('HOSPITAL_ADMIN_BOOTSTRAP_JSON')
    bootstrap = {}
    if raw_bootstrap:
        try:
            bootstrap = json.loads(raw_bootstrap)
        except (TypeError, ValueError):
            raise RuntimeError('Hospital admin bootstrap must be valid JSON.') from None
        expected = {spec['slug'] for spec in HOSPITALS}
        if not isinstance(bootstrap, dict) or set(bootstrap) != expected:
            raise RuntimeError('Hospital admin bootstrap must contain exactly the six hospital usernames.')
        if any(not isinstance(value, str) or not 10 <= len(value) <= 128
               or not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value)
               for value in bootstrap.values()):
            raise RuntimeError('Each hospital bootstrap password must have 10-128 characters, letters and numbers.')
        create_admin_accounts = True
    credentials = []
    for spec in HOSPITALS:
        hospital = db.session.scalar(db.select(Hospital).where(Hospital.slug == spec['slug']))
        if not hospital:
            hospital = Hospital(**{key: spec[key] for key in ('slug', 'name', 'city', 'area', 'address', 'hospital_type', 'phone', 'source_url')},
                                contact_checked_at=CHECKED_AT, operational_verified=False)
            db.session.add(hospital)
            db.session.flush()
        username = spec['slug']
        if create_admin_accounts and not db.session.scalar(db.select(User.id).where(User.username == username)):
            password = bootstrap.get(username)
            password = password or (current_app.config.get('SEED_ADMIN_PASSWORD') if current_app.testing else None)
            password = password or secrets.token_urlsafe(20)
            admin = User(name=f'{spec["name"][:55]} workspace admin', email=f'{username}@workspaces.medibed.invalid',
                         username=username, role='hospital_admin', hospital_id=hospital.id, password_hash=generate_password_hash(password))
            db.session.add(admin)
            db.session.flush()
            db.session.add(Notification(user_id=admin.id, title='Your workspace is ready',
                message='This project-managed account is not proof of hospital authorization. Inventory and requests remain internal until institutional onboarding.'))
            credentials.append((username, password, hospital.name))
        if spec['ambulance_phone'] and not db.session.scalar(db.select(Ambulance.id).where(Ambulance.hospital_id == hospital.id)):
            db.session.add(Ambulance(hospital_id=hospital.id, provider_name=f'{hospital.name} ambulance contact', city='Pune', area=hospital.area,
                status='unknown', estimated_arrival_minutes=None, ambulance_type='Confirm vehicle type with dispatcher',
                phone=spec['ambulance_phone'], alternate_phone=spec['ambulance_alternate'], contact_label=spec['contact_label'],
                source_url=spec.get('ambulance_source', spec['source_url']), contact_checked_at=CHECKED_AT))
    db.session.flush()
    seed_synthetic_inventory()
    if credentials and not current_app.testing:
        path = Path(current_app.config['INSTANCE_DIRECTORY']) / 'admin-credentials.txt'
        with path.open('a', encoding='utf-8') as stream:
            for username, password, hospital_name in credentials:
                stream.write(f'{hospital_name}\nUsername: {username}\nPassword: {password}\n\n')
        if os.name != 'nt':
            path.chmod(0o600)
    db.session.commit()


if __name__ == '__main__':
    from app import create_app
    app = create_app({'AUTO_SEED': False})
    with app.app_context():
        seed_data()
        print('Pune directory initialized. Existing records preserved.')
        print('Private credential file:', Path(app.config['INSTANCE_DIRECTORY']) / 'admin-credentials.txt')
