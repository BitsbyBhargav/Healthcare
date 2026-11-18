from models import db, Bed, Hospital, BedHistory, iso, now


def counts(beds):
    result = {s: sum(b.status == s for b in beds) for s in ('available', 'occupied', 'reserved', 'maintenance')}
    result['total'] = len(beds)
    result['by_type'] = {t: {'total': sum(b.bed_type == t for b in beds), 'available': sum(b.bed_type == t and b.status == 'available' for b in beds)} for t in ('general', 'icu', 'emergency')}
    result['oxygen_available'] = sum(b.status == 'available' and b.has_oxygen for b in beds)
    result['ventilator_available'] = sum(b.status == 'available' and b.has_ventilator for b in beds)
    return result


def hospital_data(hospital):
    has_synthetic_inventory = any(bed.bed_code.startswith('KAG-') for bed in hospital.beds)
    return {k: getattr(hospital, k) for k in ('id', 'name', 'city', 'area', 'address', 'hospital_type', 'phone')} | {
        'last_updated': iso(hospital.last_updated), 'inventory': counts(hospital.beds),
        'slug': hospital.slug, 'source_url': hospital.source_url, 'contact_checked_at': iso(hospital.contact_checked_at),
        'tel_uri': 'tel:' + hospital.phone, 'operational_verified': hospital.operational_verified,
        'has_inventory': bool(hospital.beds),
        'inventory_source': 'synthetic_kaggle' if has_synthetic_inventory else 'hospital_reported' if hospital.operational_verified else 'workspace_unverified' if hospital.beds else 'not_connected',
        'availability_notice': 'Synthetic Kaggle-derived demo inventory. These illustrative figures are not supplied by or verified with the hospital; call to confirm actual availability.' if has_synthetic_inventory else
            'Confirm current availability directly with the hospital.' if hospital.operational_verified else
            'Hospital inventory is not connected. Any workspace figures are unverified and do not represent confirmed hospital availability.',
    }


def touch(hospital_id):
    db.session.execute(db.update(Hospital).where(Hospital.id == hospital_id).values(last_updated=now()))
    db.session.flush()
    # Keep today's observed snapshot distinct from the seeded synthetic history.
    for kind in ('general', 'icu', 'emergency'):
        total = db.session.scalar(db.select(db.func.count(Bed.id)).where(Bed.hospital_id == hospital_id, Bed.bed_type == kind))
        available = db.session.scalar(db.select(db.func.count(Bed.id)).where(Bed.hospital_id == hospital_id, Bed.bed_type == kind, Bed.status == 'available'))
        row = db.session.scalar(db.select(BedHistory).where(BedHistory.hospital_id == hospital_id, BedHistory.bed_type == kind, BedHistory.recorded_date == now().date()))
        if not row:
            row = BedHistory(hospital_id=hospital_id, bed_type=kind, recorded_date=now().date())
            db.session.add(row)
        row.total_beds, row.available_beds, row.source = total, available, 'workspace_unverified'
