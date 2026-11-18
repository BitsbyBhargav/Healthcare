from models import db, User, Notification, AdmissionRequest


def notify(user_id, title, message):
    db.session.add(Notification(user_id=user_id, title=title, message=message))


def notify_admins(hospital_id, title, message):
    for admin in db.session.scalars(db.select(User).where(User.role == 'hospital_admin', User.hospital_id == hospital_id)):
        notify(admin.id, title, message)


def notify_waitlist(bed):
    for req in db.session.scalars(db.select(AdmissionRequest).where(
        AdmissionRequest.hospital_id == bed.hospital_id, AdmissionRequest.status == 'waitlisted',
        AdmissionRequest.requested_bed_type == bed.bed_type)):
        if (not req.oxygen_required or bed.has_oxygen) and (not req.ventilator_required or bed.has_ventilator):
            notify(req.patient_id, 'A matching workspace bed is available',
                   f'A workspace {bed.bed_type.upper()} bed matching request #{req.id} is available. Your request remains waitlisted. These figures are unverified; contact the hospital for actual availability.')
