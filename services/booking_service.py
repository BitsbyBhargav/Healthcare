from flask import abort
from sqlalchemy.exc import OperationalError, IntegrityError
from models import db, Bed, AdmissionRequest, now
from services.inventory import touch
from services.notification_service import notify, notify_admins, notify_waitlist
from services.security import audit


def eligible(hospital_id, bed_type, oxygen=False, ventilator=False):
    statement = db.select(Bed).where(Bed.hospital_id == hospital_id, Bed.bed_type == bed_type, Bed.status == 'available')
    if oxygen:
        statement = statement.where(Bed.has_oxygen.is_(True))
    if ventilator:
        statement = statement.where(Bed.has_ventilator.is_(True))
    # Prefer the least equipped eligible bed, preserving scarce capabilities.
    return statement.order_by(Bed.has_ventilator, Bed.has_oxygen, Bed.id)


def decide(req, decision):
    if req.status not in ('pending', 'waitlisted'):
        abort(409, description='This request has already been decided or cancelled.')
    try:
        bed = None
        if decision == 'approve':
            bed = db.session.scalar(eligible(req.hospital_id, req.requested_bed_type, req.oxygen_required, req.ventilator_required))
            if not bed:
                abort(409, description='No matching available bed. Keep this request on the waiting list or try again later.')
            claimed = db.session.execute(db.update(Bed).where(
                Bed.id == bed.id, Bed.hospital_id == req.hospital_id, Bed.status == 'available',
                Bed.bed_type == req.requested_bed_type,
                *([Bed.has_oxygen.is_(True)] if req.oxygen_required else []),
                *([Bed.has_ventilator.is_(True)] if req.ventilator_required else []),
            ).values(status='reserved', updated_at=now()).execution_options(synchronize_session=False))
            if claimed.rowcount != 1:
                db.session.rollback()
                abort(409, description='Another request reserved this bed. Please refresh and try again.')
        status = 'approved' if decision == 'approve' else 'rejected'
        updated = db.session.execute(db.update(AdmissionRequest).where(
            AdmissionRequest.id == req.id, AdmissionRequest.status.in_(('pending', 'waitlisted')),
        ).values(status=status, assigned_bed_id=bed.id if bed else None, decided_at=now()).execution_options(synchronize_session=False))
        if updated.rowcount != 1:
            db.session.rollback()
            abort(409, description='This request changed. Please refresh.')
        if bed:
            touch(req.hospital_id)
        notify(req.patient_id, f'Workspace request {status}',
               f'Request #{req.id} in the {req.hospital.name} workspace was {status}.' + (f' Workspace bed {bed.bed_code} is reserved. This is not hospital confirmation or a medical admission.' if bed else ' No beds were changed.'))
        audit(f'request.{status}', req.hospital_id, req.id)
        db.session.commit()
        db.session.expire_all()
        return db.session.get(AdmissionRequest, req.id)
    except (OperationalError, IntegrityError):
        db.session.rollback()
        abort(409, description='The inventory changed during this action. Refresh and try again.')


def cancel(req):
    old_status = req.status
    if old_status not in ('pending', 'waitlisted', 'approved'):
        abort(409, description='Only active requests or reservations can be cancelled.')
    try:
        result = db.session.execute(db.update(AdmissionRequest).where(
            AdmissionRequest.id == req.id, AdmissionRequest.status == old_status,
        ).values(status='cancelled', decided_at=now()).execution_options(synchronize_session=False))
        if result.rowcount != 1:
            db.session.rollback()
            abort(409, description='The request changed. Refresh and try again.')
        if old_status == 'approved' and req.assigned_bed_id:
            # Never release an occupied bed, nor a reservation attached to a different active request.
            other = db.session.scalar(db.select(AdmissionRequest.id).where(
                AdmissionRequest.assigned_bed_id == req.assigned_bed_id,
                AdmissionRequest.status == 'approved', AdmissionRequest.id != req.id))
            if not other:
                released = db.session.execute(db.update(Bed).where(
                    Bed.id == req.assigned_bed_id, Bed.hospital_id == req.hospital_id, Bed.status == 'reserved',
                ).values(status='available', updated_at=now()).execution_options(synchronize_session=False))
                if released.rowcount:
                    touch(req.hospital_id)
                    db.session.expire_all()
                    notify_waitlist(db.session.get(Bed, req.assigned_bed_id))
        notify(req.patient_id, 'Request cancelled', f'Your workspace request #{req.id} was cancelled.')
        notify_admins(req.hospital_id, 'Patient cancelled a request', f'Workspace request #{req.id} was cancelled by the patient.')
        audit('request.cancelled', req.hospital_id, req.id)
        db.session.commit()
        db.session.expire_all()
        return db.session.get(AdmissionRequest, req.id)
    except (OperationalError, IntegrityError):
        db.session.rollback()
        abort(409, description='The request changed during cancellation. Please refresh.')
