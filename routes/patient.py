from flask import Blueprint, g, abort, request
from models import db, Hospital, AdmissionRequest, BED_TYPES, REQUEST_STATUSES
from services.common import success, body, role_required, choice, boolean, integer
from services.booking_service import eligible, cancel
from services.notification_service import notify, notify_admins
from services.security import audit

bp = Blueprint('patient', __name__)


@bp.post('/api/requests')
@role_required('patient')
def create_request():
    data = body()
    hospital = db.get_or_404(Hospital, integer(data.get('hospital_id'), 'Hospital'))
    if not hospital.operational_verified and data.get('acknowledge_unverified') is not True:
        abort(400, description='Acknowledge that this request stays within the independent MediBed workspace and is not sent to the hospital.')
    bed_type = choice(data.get('requested_bed_type'), BED_TYPES, 'Bed type')
    priority = choice(data.get('priority', 'normal'), ('normal', 'emergency'), 'Priority')
    ventilator = boolean(data, 'ventilator_required')
    oxygen = boolean(data, 'oxygen_required') or ventilator
    waitlist = boolean(data, 'join_waitlist')
    duplicate = db.session.scalar(db.select(AdmissionRequest.id).where(
        AdmissionRequest.patient_id == g.user.id, AdmissionRequest.hospital_id == hospital.id,
        AdmissionRequest.requested_bed_type == bed_type, AdmissionRequest.oxygen_required == oxygen,
        AdmissionRequest.ventilator_required == ventilator, AdmissionRequest.status.in_(('pending', 'waitlisted', 'approved'))))
    if duplicate:
        abort(409, description='You already have an active matching request at this hospital. Review it in My requests.')
    available = db.session.scalar(eligible(hospital.id, bed_type, oxygen, ventilator))
    if not available and not waitlist:
        abort(409, description='No matching workspace beds are available. Select the waiting-list option to continue. Contact the hospital for actual availability.')
    status = 'waitlisted' if not available else 'pending'
    req = AdmissionRequest(patient_id=g.user.id, hospital_id=hospital.id, requested_bed_type=bed_type,
                           oxygen_required=oxygen, ventilator_required=ventilator, priority=priority, status=status)
    db.session.add(req)
    db.session.flush()
    notify_admins(hospital.id, 'New workspace request', f'Request #{req.id}: {bed_type.upper()}, {priority} priority ({status}). Priority is a sorting aid, not clinical triage.')
    notify(g.user.id, 'Waiting list joined' if status == 'waitlisted' else 'Admission request submitted',
           f'Request #{req.id} for the {hospital.name} workspace is {status}. This is internal to MediBed; no hospital admission is confirmed.')
    audit('request.created', hospital.id, req.id)
    db.session.commit()
    return success(req.public(), 'Workspace request recorded. No hospital admission is confirmed.', 201)


@bp.get('/api/requests/mine')
@role_required('patient')
def mine():
    stmt = db.select(AdmissionRequest).where(AdmissionRequest.patient_id == g.user.id)
    if request.args.get('status'):
        stmt = stmt.where(AdmissionRequest.status == choice(request.args['status'], REQUEST_STATUSES, 'Status'))
    return success({'requests': [r.public() for r in db.session.scalars(stmt.order_by(AdmissionRequest.created_at.desc(), AdmissionRequest.id.desc()))]})


@bp.post('/api/requests/<int:request_id>/cancel')
@role_required('patient')
def cancel_request(request_id):
    req = db.get_or_404(AdmissionRequest, request_id)
    if req.patient_id != g.user.id:
        abort(403, description='You can only cancel your own requests.')
    return success(cancel(req).public(), 'Workspace request cancelled.')
