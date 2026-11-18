from models import db, Bed, Hospital, AdmissionRequest, User, Ambulance, BedHistory, Notification
from seed import seed_data


def test_search_filters_and_physical_counts(app):
    c = app.test_client()
    all_data = c.get('/api/hospitals').json['data']
    assert all_data['count'] == 6
    assert all(h['inventory_source'] == 'synthetic_kaggle' for h in all_data['hospitals'])
    rows = c.get('/api/hospitals?city=Pune&bed_type=icu&oxygen_required=true&ventilator_required=true').json['data']['hospitals']
    assert rows and all(h['city'] == 'Pune' and h['inventory']['ventilator_available'] > 0 for h in rows)
    assert c.get('/api/hospitals?bed_type=unknown').status_code == 400
    assert c.get('/api/hospitals?oxygen_required=oops').status_code == 400
    for hospital in all_data['hospitals']:
        inv = hospital['inventory']
        assert inv['total'] == sum(v['total'] for v in inv['by_type'].values())
        assert inv['total'] == sum(inv[s] for s in ['available','occupied','reserved','maintenance'])


def test_inventory_updates_public_counts(admin, patient):
    before = patient.get('/api/hospitals/1').json['data']['inventory']['available']
    beds = admin.get('/api/admin/beds?status=available').json['data']['beds']
    bed = beds[0]
    result = admin.send('PATCH', f'/api/admin/beds/{bed["id"]}', {'status': 'occupied'})
    assert result.status_code == 200, result.json
    assert patient.get('/api/hospitals/1').json['data']['inventory']['available'] == before-1
    assert admin.get('/api/dashboard/stats?scope=admin').json['data']['available'] == before-1


def test_admin_ownership_and_reserved_protection(app, admin):
    with app.app_context():
        other = db.session.scalar(db.select(Bed.id).where(Bed.hospital_id == 2))
        reserved = db.session.scalar(db.select(Bed.id).where(Bed.hospital_id == 1, Bed.status == 'reserved'))
        req = db.session.scalar(db.select(AdmissionRequest.id).where(AdmissionRequest.hospital_id == 2))
    assert admin.send('PATCH', f'/api/admin/beds/{other}', {'status': 'occupied'}).status_code == 403
    assert admin.send('DELETE', f'/api/admin/beds/{other}').status_code == 403
    assert admin.get('/api/admin/beds?hospital_id=2').status_code == 403
    assert admin.get('/api/admin/requests?hospital_id=2').status_code == 403
    assert admin.send('POST', f'/api/admin/requests/{req}/decision', {'decision': 'approve'}).status_code == 403
    assert admin.send('PATCH', f'/api/admin/beds/{reserved}', {'status': 'available'}).status_code == 409
    assert admin.send('DELETE', f'/api/admin/beds/{reserved}').status_code == 409


def test_bed_crud_and_validation(admin):
    fields = {'bed_code': 'TEST-001', 'bed_type': 'icu', 'has_oxygen': True, 'has_ventilator': True}
    result = admin.send('POST', '/api/admin/beds', fields)
    assert result.status_code == 201
    bed_id = result.json['data']['id']
    assert admin.send('POST', '/api/admin/beds', fields).status_code == 409
    assert admin.send('PATCH', f'/api/admin/beds/{bed_id}', {'has_oxygen': False}).status_code == 400
    assert admin.send('PATCH', f'/api/admin/beds/{bed_id}', {'has_oxygen': 'false'}).status_code == 400
    assert admin.send('PATCH', f'/api/admin/beds/{bed_id}', {'status': 'reserved'}).status_code == 409
    assert admin.send('PATCH', f'/api/admin/beds/{bed_id}', {'hospital_id': 2}).status_code == 403
    assert admin.send('PATCH', f'/api/admin/beds/{bed_id}', {'status': 'maintenance'}).status_code == 200
    assert admin.send('DELETE', f'/api/admin/beds/{bed_id}').status_code == 200
    assert admin.send('DELETE', f'/api/admin/beds/{bed_id}').status_code == 404


def test_seed_idempotence(app):
    with app.app_context():
        models = [User, Hospital, Bed, AdmissionRequest, Ambulance, BedHistory, Notification]
        before = [db.session.scalar(db.select(db.func.count(m.id))) for m in models]
        bed = db.session.scalar(db.select(Bed).where(Bed.status == 'available'))
        bed.status = 'occupied'
        bed_id = bed.id
        db.session.commit()
        seed_data()
        after = [db.session.scalar(db.select(db.func.count(m.id))) for m in models]
        assert before == after
        assert db.session.get(Bed, bed_id).status == 'occupied'
        for hospital in db.session.scalars(db.select(Hospital)):
            assert db.session.scalar(db.select(User.id).where(User.role == 'hospital_admin', User.hospital_id == hospital.id))


def test_kaggle_demo_inventory_and_history_are_labeled(app):
    with app.app_context():
        hospital = db.session.get(Hospital, 1)
        beds = db.session.scalars(db.select(Bed).where(Bed.hospital_id == hospital.id)).all()
        history = db.session.scalars(db.select(BedHistory).where(BedHistory.hospital_id == hospital.id)).all()
        assert beds and all(bed.bed_code.startswith('KAG-') for bed in beds)
        assert {bed.bed_type for bed in beds} == {'general', 'icu', 'emergency'}
        assert len(history) == 3 * 45
        assert {row.source for row in history} == {'synthetic_kaggle'}
        assert all(0 <= row.available_beds <= row.total_beds for row in history)
