import re
from datetime import timedelta
from flask import Blueprint, abort, g, request
from sqlalchemy.exc import IntegrityError, OperationalError
from models import db, Bed, AdmissionRequest, Ambulance, AuditEvent, BED_TYPES, BED_STATUSES, REQUEST_STATUSES, now, iso
from services.common import body, success, role_required, choice, boolean, integer, text
from services.inventory import touch
from services.booking_service import decide
from services.notification_service import notify_waitlist
from services.security import audit

bp = Blueprint('admin', __name__, url_prefix='/api/admin')


def owned(model, record_id):
    record = db.get_or_404(model, record_id)
    if record.hospital_id != g.user.hospital_id:
        abort(403, description='This record belongs to another hospital.')
    return record


def check_scope():
    if request.args.get('hospital_id') and integer(request.args['hospital_id'], 'Hospital') != g.user.hospital_id:
        abort(403, description='You can only access your assigned hospital.')


@bp.get('/beds')
@role_required('hospital_admin')
def beds():
    check_scope()
    stmt = db.select(Bed).where(Bed.hospital_id == g.user.hospital_id)
    for key, options in (('status', BED_STATUSES), ('bed_type', BED_TYPES)):
        if request.args.get(key):
            stmt = stmt.where(getattr(Bed, key) == choice(request.args[key], options, key))
    return success({'beds': [b.public() for b in db.session.scalars(stmt.order_by(Bed.id))]})


def bed_values(data, bed=None):
    if 'hospital_id' in data and integer(data['hospital_id'], 'Hospital') != g.user.hospital_id:
        abort(403, description='You cannot transfer inventory between hospitals.')
    allowed = {'bed_code', 'bed_type', 'has_oxygen', 'has_ventilator', 'status', 'hospital_id'}
    if set(data) - allowed:
        abort(400, description='Unknown bed field.')
    code = text(data.get('bed_code', bed.bed_code if bed else None), 'Bed code', 1, 24).upper()
    if not re.fullmatch(r'[A-Z0-9-]+', code):
        abort(400, description='Bed code may contain letters, numbers and hyphens.')
    bed_type = choice(data.get('bed_type', bed.bed_type if bed else None), BED_TYPES, 'Bed type')
    status = choice(data.get('status', bed.status if bed else 'available'), BED_STATUSES, 'Status')
    if status == 'reserved':
        abort(409, description='Beds are reserved only through admission approval.')
    oxygen = boolean(data, 'has_oxygen', bed.has_oxygen if bed else False)
    ventilator = boolean(data, 'has_ventilator', bed.has_ventilator if bed else False)
    if ventilator and not oxygen:
        abort(400, description='Ventilator-capable beds must also have oxygen capability.')
    return dict(bed_code=code, bed_type=bed_type, status=status, has_oxygen=oxygen, has_ventilator=ventilator, updated_at=now())


def save_inventory(bed, became_available):
    touch(g.user.hospital_id)
    db.session.flush()
    if became_available:
        notify_waitlist(bed)
    audit('inventory.saved', g.user.hospital_id, bed.id)
    db.session.commit()


@bp.post('/beds')
@role_required('hospital_admin')
def add_bed():
    bed = Bed(hospital_id=g.user.hospital_id, **bed_values(body()))
    db.session.add(bed)
    try:
        save_inventory(bed, bed.status == 'available')
    except IntegrityError:
        db.session.rollback()
        abort(409, description='That bed code already exists in this hospital.')
    return success(bed.public(), 'Bed added.', 201)


@bp.patch('/beds/<int:bed_id>')
@role_required('hospital_admin')
def update_bed(bed_id):
    bed = owned(Bed, bed_id)
    if bed.status == 'reserved' or db.session.scalar(db.select(AdmissionRequest.id).where(AdmissionRequest.assigned_bed_id == bed.id, AdmissionRequest.status == 'approved')):
        abort(409, description='This bed is allocated to a reservation. Cancel it through the patient workflow first.')
    values = bed_values(body(), bed)
    changed = values['status'] == 'available' and (bed.status != 'available' or any(values[k] != getattr(bed, k) for k in ('bed_type', 'has_oxygen', 'has_ventilator')))
    try:
        result = db.session.execute(db.update(Bed).where(Bed.id == bed.id, Bed.status == bed.status,
            ~db.select(AdmissionRequest.id).where(AdmissionRequest.assigned_bed_id == Bed.id, AdmissionRequest.status == 'approved').exists()
        ).values(**values).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            db.session.rollback()
            abort(409, description='This bed changed or was reserved. Please refresh.')
        db.session.expire(bed)
        save_inventory(bed, changed)
    except (IntegrityError, OperationalError):
        db.session.rollback()
        abort(409, description='Bed code exists or inventory changed. Refresh and try again.')
    return success(bed.public(), 'Inventory updated.')


@bp.delete('/beds/<int:bed_id>')
@role_required('hospital_admin')
def delete_bed(bed_id):
    bed = owned(Bed, bed_id)
    if bed.status not in ('available', 'maintenance'):
        abort(409, description='Only unallocated available or maintenance beds can be deleted.')
    try:
        result = db.session.execute(db.delete(Bed).where(Bed.id == bed_id, Bed.status.in_(('available', 'maintenance')),
            ~db.select(AdmissionRequest.id).where(AdmissionRequest.assigned_bed_id == Bed.id).exists()))
        if result.rowcount != 1:
            db.session.rollback()
            abort(409, description='This bed has reservation history or changed. It cannot be deleted.')
        touch(g.user.hospital_id)
        audit('inventory.deleted', g.user.hospital_id, bed_id)
        db.session.commit()
    except (IntegrityError, OperationalError):
        db.session.rollback()
        abort(409, description='This bed is allocated or changed. Refresh and try again.')
    return success(None, 'Bed deleted.')


@bp.get('/requests')
@role_required('hospital_admin')
def requests_list():
    check_scope()
    stmt = db.select(AdmissionRequest).where(AdmissionRequest.hospital_id == g.user.hospital_id)
    if request.args.get('status'):
        stmt = stmt.where(AdmissionRequest.status == choice(request.args['status'], REQUEST_STATUSES, 'Status'))
    stmt = stmt.order_by(db.case((AdmissionRequest.priority == 'emergency', 0), else_=1), AdmissionRequest.created_at, AdmissionRequest.id)
    return success({'requests': [r.public(admin=True) for r in db.session.scalars(stmt)]})


@bp.post('/requests/<int:request_id>/decision')
@role_required('hospital_admin')
def decision(request_id):
    req = owned(AdmissionRequest, request_id)
    decision = choice(body().get('decision'), ('approve', 'reject'), 'Decision')
    return success(decide(req, decision).public(admin=True), 'Workspace decision recorded.')


@bp.get('/ambulances')
@role_required('hospital_admin')
def ambulance_contacts():
    check_scope()
    rows = db.session.scalars(db.select(Ambulance).where(Ambulance.hospital_id == g.user.hospital_id).order_by(Ambulance.id))
    return success({'ambulances': [row.public() for row in rows]})


@bp.patch('/ambulances/<int:ambulance_id>')
@role_required('hospital_admin')
def report_ambulance_status(ambulance_id):
    record = owned(Ambulance, ambulance_id)
    data = body()
    if set(data) - {'status'}:
        abort(400, description='Only availability status can be updated. Published contact details are curated separately.')
    record.status = choice(data.get('status'), ('unknown', 'available', 'busy'), 'Status')
    record.status_updated_at = now()
    record.status_expires_at = now() + timedelta(minutes=30) if record.status != 'unknown' else None
    audit('ambulance.status_reported', g.user.hospital_id, record.id)
    db.session.commit()
    return success(record.public(), 'Workspace report saved for 30 minutes. It is not independent verification of vehicle availability.')


@bp.get('/audit')
@role_required('hospital_admin')
def audit_events():
    check_scope()
    rows = db.session.scalars(db.select(AuditEvent).where(AuditEvent.hospital_id == g.user.hospital_id).order_by(AuditEvent.id.desc()).limit(100))
    return success({'events': [{'id': row.id, 'action': row.action, 'record_id': row.record_id, 'actor_id': row.actor_id, 'created_at': iso(row.created_at)} for row in rows]})
