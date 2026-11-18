from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import event
from sqlalchemy.engine import Engine

db = SQLAlchemy()
BED_TYPES = ('general', 'icu', 'emergency')
BED_STATUSES = ('available', 'occupied', 'reserved', 'maintenance')
REQUEST_STATUSES = ('pending', 'waitlisted', 'approved', 'rejected', 'cancelled')


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(value):
    return value.isoformat() + 'Z' if value else None


@event.listens_for(Engine, 'connect')
def sqlite_pragmas(connection, _):
    if connection.__class__.__module__.startswith('sqlite3'):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.execute('PRAGMA busy_timeout=15000')
        cursor.close()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(254), nullable=False, unique=True)
    username = db.Column(db.String(80), unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'))
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    hospital = db.relationship('Hospital')
    __table_args__ = (
        db.CheckConstraint("role IN ('patient','hospital_admin')"),
        db.CheckConstraint("(role='patient' AND hospital_id IS NULL) OR (role='hospital_admin' AND hospital_id IS NOT NULL)"),
    )

    def public(self):
        return {'id': self.id, 'name': self.name, 'email': self.email, 'username': self.username, 'role': self.role, 'hospital_id': self.hospital_id}


class Hospital(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    city = db.Column(db.String(80), nullable=False, index=True)
    area = db.Column(db.String(80), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    hospital_type = db.Column(db.String(20), nullable=False)
    phone = db.Column(db.String(40), nullable=False)
    slug = db.Column(db.String(80), unique=True, nullable=False)
    source_url = db.Column(db.String(500), nullable=False)
    contact_checked_at = db.Column(db.DateTime, nullable=False, default=now)
    # Project workspace accounts do not establish hospital authorization.
    operational_verified = db.Column(db.Boolean, nullable=False, default=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    last_updated = db.Column(db.DateTime, default=now, nullable=False)
    beds = db.relationship('Bed', back_populates='hospital', lazy='selectin')
    __table_args__ = (db.CheckConstraint("hospital_type IN ('government','private')"),)


class Bed(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False, index=True)
    bed_code = db.Column(db.String(24), nullable=False)
    bed_type = db.Column(db.String(16), nullable=False)
    has_oxygen = db.Column(db.Boolean, default=False, nullable=False)
    has_ventilator = db.Column(db.Boolean, default=False, nullable=False)
    status = db.Column(db.String(16), default='available', nullable=False)
    updated_at = db.Column(db.DateTime, default=now, nullable=False)
    hospital = db.relationship('Hospital', back_populates='beds')
    __table_args__ = (
        db.UniqueConstraint('hospital_id', 'bed_code'),
        db.CheckConstraint("bed_type IN ('general','icu','emergency')"),
        db.CheckConstraint("status IN ('available','occupied','reserved','maintenance')"),
        db.CheckConstraint('NOT has_ventilator OR has_oxygen'),
    )

    def public(self):
        return {k: getattr(self, k) for k in ('id', 'hospital_id', 'bed_code', 'bed_type', 'has_oxygen', 'has_ventilator', 'status')} | {'updated_at': iso(self.updated_at)}


class AdmissionRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False, index=True)
    requested_bed_type = db.Column(db.String(16), nullable=False)
    oxygen_required = db.Column(db.Boolean, default=False, nullable=False)
    ventilator_required = db.Column(db.Boolean, default=False, nullable=False)
    priority = db.Column(db.String(16), default='normal', nullable=False)
    status = db.Column(db.String(16), default='pending', nullable=False)
    assigned_bed_id = db.Column(db.Integer, db.ForeignKey('bed.id'))
    created_at = db.Column(db.DateTime, default=now, nullable=False)
    decided_at = db.Column(db.DateTime)
    patient = db.relationship('User')
    hospital = db.relationship('Hospital')
    assigned_bed = db.relationship('Bed')
    __table_args__ = (
        db.CheckConstraint("requested_bed_type IN ('general','icu','emergency')"),
        db.CheckConstraint("priority IN ('normal','emergency')"),
        db.CheckConstraint("status IN ('pending','waitlisted','approved','rejected','cancelled')"),
        db.CheckConstraint("status != 'approved' OR assigned_bed_id IS NOT NULL"),
        db.Index('one_active_reservation_per_bed', 'assigned_bed_id', unique=True,
                 sqlite_where=db.text("status = 'approved'"),
                 postgresql_where=db.text("status = 'approved'")),
    )

    def public(self, admin=False):
        data = {k: getattr(self, k) for k in ('id', 'hospital_id', 'requested_bed_type', 'oxygen_required', 'ventilator_required', 'priority', 'status', 'assigned_bed_id')}
        data.update(hospital_name=self.hospital.name, bed_code=self.assigned_bed.bed_code if self.assigned_bed else None,
                    created_at=iso(self.created_at), decided_at=iso(self.decided_at),
                    delivery_status='hospital_connected' if self.hospital.operational_verified else 'internal_only',
                    hospital_confirmed=self.hospital.operational_verified and self.status == 'approved')
        if admin:
            data.update(patient_name=self.patient.name)
        return data


class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=now, nullable=False)

    def public(self):
        return {'id': self.id, 'title': self.title, 'message': self.message, 'is_read': self.is_read, 'created_at': iso(self.created_at)}


class Ambulance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider_name = db.Column(db.String(120), unique=True, nullable=False)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False, index=True)
    city = db.Column(db.String(80), nullable=False)
    area = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    estimated_arrival_minutes = db.Column(db.Integer)
    ambulance_type = db.Column(db.String(60), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    alternate_phone = db.Column(db.String(20))
    contact_label = db.Column(db.String(80), nullable=False)
    source_url = db.Column(db.String(500), nullable=False)
    contact_checked_at = db.Column(db.DateTime, default=now, nullable=False)
    status_updated_at = db.Column(db.DateTime)
    status_expires_at = db.Column(db.DateTime)
    hospital = db.relationship('Hospital')
    __table_args__ = (db.CheckConstraint('estimated_arrival_minutes IS NULL OR estimated_arrival_minutes >= 0'), db.CheckConstraint("status IN ('available','busy','unknown')"))

    def public(self):
        effective_status = self.status if self.status_expires_at and self.status_expires_at > now() else 'unknown'
        verified = bool(self.hospital.operational_verified)
        return {k: getattr(self, k) for k in ('id', 'hospital_id', 'provider_name', 'city', 'area', 'ambulance_type', 'phone', 'alternate_phone', 'contact_label', 'source_url')} | {
            'hospital_name': self.hospital.name, 'status': effective_status,
            'availability_source': 'hospital_reported' if verified and effective_status != 'unknown' else 'workspace_unverified' if effective_status != 'unknown' else 'not_connected',
            'availability_label': 'Call to confirm' if effective_status == 'unknown' else ('Hospital reported ' if verified else 'Workspace reported ') + effective_status,
            'contact_checked_at': iso(self.contact_checked_at), 'status_updated_at': iso(self.status_updated_at),
            'status_expires_at': iso(self.status_expires_at), 'tel_uri': 'tel:' + self.phone,
            'alternate_tel_uri': 'tel:' + self.alternate_phone if self.alternate_phone else None,
            'estimated_arrival_minutes': None,
            'disclaimer': 'Published dispatch contact. A call does not reserve or dispatch a vehicle. Confirm availability, charges and arrival time with the operator.',
        }


class BedHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'), nullable=False)
    bed_type = db.Column(db.String(16), nullable=False)
    recorded_date = db.Column(db.Date, nullable=False)
    total_beds = db.Column(db.Integer, nullable=False)
    available_beds = db.Column(db.Integer, nullable=False)
    source = db.Column(db.String(32), nullable=False, default='workspace_unverified')
    __table_args__ = (
        db.UniqueConstraint('hospital_id', 'bed_type', 'recorded_date'),
        db.CheckConstraint('available_beds >= 0 AND available_beds <= total_beds'),
        db.CheckConstraint("bed_type IN ('general','icu','emergency')"),
    )


class RateBucket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), nullable=False)
    window = db.Column(db.Integer, nullable=False)
    attempts = db.Column(db.Integer, nullable=False, default=1)
    __table_args__ = (db.UniqueConstraint('key', 'window'),)


class AuditEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    hospital_id = db.Column(db.Integer, db.ForeignKey('hospital.id'))
    action = db.Column(db.String(80), nullable=False)
    record_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=now, nullable=False)
