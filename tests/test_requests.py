from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from models import db, Bed, AdmissionRequest, User
from conftest import APIClient


def new_request(patient, **overrides):
    fields = {'hospital_id': 1, 'requested_bed_type': 'general', 'priority': 'normal'} | overrides
    result = patient.send('POST', '/api/requests', fields)
    assert result.status_code == 201, result.json
    return result.json['data']


def test_full_admission_approval_cancel_flow(app, patient, admin):
    before = patient.get('/api/hospitals/1').json['data']['inventory']['available']
    req = new_request(patient, requested_bed_type='icu', oxygen_required=True, ventilator_required=True, priority='emergency')
    assert req['status'] == 'pending' and req['assigned_bed_id'] is None
    assert any(r['id'] == req['id'] for r in admin.get('/api/admin/requests').json['data']['requests'])
    assert any(n['title'] == 'New demo admission request' for n in admin.get('/api/notifications').json['data']['notifications'])
    result = admin.send('POST', f'/api/admin/requests/{req["id"]}/decision', {'decision': 'approve'})
    assert result.status_code == 200, result.json
    approved = result.json['data']
    with app.app_context():
        bed = db.session.get(Bed, approved['assigned_bed_id'])
        assert bed.status == 'reserved' and bed.bed_type == 'icu' and bed.has_oxygen and bed.has_ventilator and bed.hospital_id == 1
    assert patient.get('/api/hospitals/1').json['data']['inventory']['available'] == before-1
    assert any(r['id'] == req['id'] and r['status'] == 'approved' for r in patient.get('/api/requests/mine').json['data']['requests'])
    assert any(n['title'] == 'Demo request approved' for n in patient.get('/api/notifications').json['data']['notifications'])
    assert admin.send('POST', f'/api/admin/requests/{req["id"]}/decision', {'decision': 'approve'}).status_code == 409
    assert patient.send('POST', f'/api/requests/{req["id"]}/cancel').status_code == 200
    assert patient.get('/api/hospitals/1').json['data']['inventory']['available'] == before


def test_rejection_does_not_change_inventory(patient, admin):
    before = patient.get('/api/hospitals/1').json['data']['inventory']
    req = new_request(patient)
    result = admin.send('POST', f'/api/admin/requests/{req["id"]}/decision', {'decision': 'reject'})
    assert result.status_code == 200 and result.json['data']['status'] == 'rejected'
    assert patient.get('/api/hospitals/1').json['data']['inventory'] == before
    assert patient.send('POST', f'/api/requests/{req["id"]}/cancel').status_code == 409


def test_waitlist_notification_no_autoapproval(app, patient, admin):
    with app.app_context():
        db.session.execute(db.update(Bed).where(Bed.hospital_id == 1, Bed.bed_type == 'emergency').values(status='occupied'))
        db.session.commit()
    assert patient.send('POST', '/api/requests', {'hospital_id': 1, 'requested_bed_type': 'emergency'}).status_code == 409
    req = new_request(patient, requested_bed_type='emergency', join_waitlist=True)
    assert req['status'] == 'waitlisted'
    bed_id = admin.get('/api/admin/beds?bed_type=emergency').json['data']['beds'][0]['id']
    assert admin.send('PATCH', f'/api/admin/beds/{bed_id}', {'status': 'available'}).status_code == 200
    notes = patient.get('/api/notifications').json['data']['notifications']
    assert any(n['title'] == 'A matching demo bed is available' for n in notes)
    assert next(r for r in patient.get('/api/requests/mine').json['data']['requests'] if r['id']==req['id'])['status']=='waitlisted'
    assert admin.send('POST', f'/api/admin/requests/{req["id"]}/decision', {'decision': 'approve'}).status_code == 200


def test_cancel_pending_and_ownership(app, patient, admin):
    req = new_request(patient)
    sample = APIClient(app)
    sample.login('sample@medibed.demo')
    assert sample.send('POST', f'/api/requests/{req["id"]}/cancel').status_code == 403
    assert patient.send('POST', f'/api/requests/{req["id"]}/cancel').status_code == 200
    note = patient.get('/api/notifications').json['data']['notifications'][0]
    assert admin.send('POST', f'/api/notifications/{note["id"]}/read').status_code == 403
    assert patient.send('POST', f'/api/notifications/{note["id"]}/read').status_code == 200


def test_cancellation_never_releases_occupied(app, patient, admin):
    req = new_request(patient)
    approved = admin.send('POST', f'/api/admin/requests/{req["id"]}/decision', {'decision': 'approve'}).json['data']
    with app.app_context():
        db.session.get(Bed, approved['assigned_bed_id']).status = 'occupied'
        db.session.commit()
    assert patient.send('POST', f'/api/requests/{req["id"]}/cancel').status_code == 200
    with app.app_context():
        assert db.session.get(Bed, approved['assigned_bed_id']).status == 'occupied'


def test_competing_approvals_only_one_wins(app, patient, admin):
    # Two independent clients race two requests for exactly one eligible ICU bed.
    with app.app_context():
        db.session.execute(db.update(Bed).where(Bed.hospital_id == 1, Bed.bed_type == 'icu').values(status='occupied'))
        bed = db.session.scalar(db.select(Bed).where(Bed.hospital_id == 1, Bed.bed_type == 'icu', Bed.has_ventilator.is_(True)))
        bed.status = 'available'
        only_bed = bed.id
        db.session.commit()
    one = new_request(patient, requested_bed_type='icu', ventilator_required=True)
    sample = APIClient(app)
    sample.login('sample@medibed.demo')
    two = new_request(sample, requested_bed_type='icu', ventilator_required=True)
    clients = [APIClient(app), APIClient(app)]
    for client in clients:
        assert client.login('admin@medibed.demo').status_code == 200
    barrier = Barrier(2)
    def approve(pair):
        client, req = pair
        barrier.wait(timeout=10)
        return client.send('POST', f'/api/admin/requests/{req["id"]}/decision', {'decision': 'approve'}).status_code
    with ThreadPoolExecutor(max_workers=2) as executor:
        codes = list(executor.map(approve, zip(clients, [one, two])))
    assert sorted(codes) == [200, 409]
    with app.app_context():
        approved = db.session.scalars(db.select(AdmissionRequest).where(AdmissionRequest.id.in_([one['id'], two['id']]), AdmissionRequest.status=='approved')).all()
        assert len(approved) == 1 and approved[0].assigned_bed_id == only_bed
        assert db.session.get(Bed, only_bed).status == 'reserved'
