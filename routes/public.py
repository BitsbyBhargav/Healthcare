from flask import Blueprint, abort, request, g, render_template, redirect, url_for
from models import db, Hospital, Bed, AdmissionRequest, Ambulance, Notification
from services.common import success, choice, query_bool, role_required, integer
from services.inventory import counts, hospital_data

bp = Blueprint('public', __name__)


@bp.get('/')
@bp.get('/hospitals')
def index():
    return render_template('index.html', hospitals=db.session.scalars(db.select(Hospital).order_by(Hospital.id)).all())


@bp.get('/hospitals/<int:hospital_id>')
def hospital_page(hospital_id):
    hospital = db.get_or_404(Hospital, hospital_id)
    return render_template('hospital_detail.html', hospital=hospital_data(hospital))


@bp.get('/login')
@bp.get('/register')
def login_page():
    if g.user:
        return redirect(url_for('public.admin_page' if g.user.role == 'hospital_admin' else 'public.patient_page'))
    return render_template('auth.html', register=request.path == '/register')


@bp.get('/patient')
def patient_page():
    if not g.user:
        return redirect(url_for('public.login_page'))
    if g.user.role != 'patient':
        abort(403)
    return render_template('patient_dashboard.html')


@bp.get('/admin')
def admin_page():
    if not g.user:
        return redirect(url_for('public.login_page'))
    if g.user.role != 'hospital_admin':
        abort(403)
    return render_template('admin_dashboard.html', hospital=g.user.hospital)


@bp.get('/ambulances')
def ambulance_page():
    return render_template('ambulances.html', hospitals=db.session.scalars(db.select(Hospital).where(Hospital.city == 'Pune').order_by(Hospital.id)).all())


@bp.get('/privacy')
def privacy_page():
    return render_template('privacy.html')


@bp.get('/predictions')
def predictions_page():
    return render_template('predictions.html', hospitals=db.session.scalars(db.select(Hospital).order_by(Hospital.id)).all())


@bp.get('/api/health')
def health():
    db.session.execute(db.text('SELECT 1'))
    return success({'status': 'healthy', 'database': 'connected', 'service': 'MediBed Pune'})


@bp.get('/api/hospitals')
def hospitals_api():
    stmt = db.select(Hospital).where(Hospital.city == 'Pune').order_by(Hospital.id)
    city = request.args.get('city', '').strip()
    category = request.args.get('hospital_type', '')
    bed_type = request.args.get('bed_type', '')
    if city:
        stmt = stmt.where(db.func.lower(Hospital.city) == city.lower())
    if request.args.get('area'):
        stmt = stmt.where(Hospital.area == request.args['area'])
    if category:
        choice(category, ('government', 'private'), 'Hospital type')
        stmt = stmt.where(Hospital.hospital_type == category)
    conditions = [Bed.hospital_id == Hospital.id, Bed.status == 'available']
    if bed_type:
        choice(bed_type, ('general', 'icu', 'emergency'), 'Bed type')
        conditions.append(Bed.bed_type == bed_type)
    oxygen, ventilator = query_bool('oxygen_required'), query_bool('ventilator_required')
    if oxygen:
        conditions.append(Bed.has_oxygen.is_(True))
    if ventilator:
        conditions.append(Bed.has_ventilator.is_(True))
    if bed_type or oxygen or ventilator or query_bool('available_only'):
        stmt = stmt.where(db.select(Bed.id).where(*conditions).exists())
    q = request.args.get('q', '').strip()[:100]
    if q:
        stmt = stmt.where(db.or_(Hospital.name.icontains(q, autoescape=True), Hospital.area.icontains(q, autoescape=True)))
    hospitals = db.session.scalars(stmt).all()
    return success({'hospitals': [hospital_data(h) for h in hospitals], 'count': len(hospitals), 'city': 'Pune'})


@bp.get('/api/hospitals/<int:hospital_id>')
def hospital_api(hospital_id):
    return success(hospital_data(db.get_or_404(Hospital, hospital_id)))


@bp.get('/api/dashboard/stats')
def stats():
    scope = request.args.get('scope', 'public')
    if scope not in ('public', 'admin'):
        abort(400, description='Scope must be public or admin.')
    statement = db.select(Bed).join(Hospital).where(Hospital.city == 'Pune')
    if scope == 'admin':
        if not g.user:
            abort(401)
        if g.user.role != 'hospital_admin':
            abort(403)
        statement = statement.where(Bed.hospital_id == g.user.hospital_id)
    data = counts(db.session.scalars(statement).all())
    data['hospital_count'] = db.session.scalar(db.select(db.func.count(Hospital.id)).where(Hospital.city == 'Pune'))
    data['cities'] = ['Pune']
    data['verified_hospital_count'] = db.session.scalar(db.select(db.func.count(Hospital.id)).where(Hospital.city == 'Pune', Hospital.operational_verified.is_(True)))
    if scope == 'public':
        data['ambulance_contacts'] = db.session.scalar(db.select(db.func.count(Ambulance.id)).where(Ambulance.city == 'Pune'))
        verified_beds = db.session.scalars(db.select(Bed).join(Hospital).where(Hospital.city == 'Pune', Hospital.operational_verified.is_(True))).all()
        verified_counts = counts(verified_beds)
        data.update(verified_counts)
        data['availability_verified'] = data['verified_hospital_count'] > 0
        if not data['availability_verified']:
            for key in ('total', 'available', 'occupied', 'reserved', 'maintenance', 'oxygen_available', 'ventilator_available'):
                data[key] = None
            data['by_type'] = {kind: {'total': None, 'available': None} for kind in ('general', 'icu', 'emergency')}
    if scope == 'admin':
        data['pending_admissions'] = db.session.scalar(db.select(db.func.count(AdmissionRequest.id)).where(
            AdmissionRequest.hospital_id == g.user.hospital_id, AdmissionRequest.status.in_(('pending', 'waitlisted'))))
        data['last_updated'] = hospital_data(g.user.hospital)['last_updated']
    return success(data)


@bp.get('/api/ambulances')
def ambulances():
    statement = db.select(Ambulance).where(Ambulance.city == 'Pune').order_by(Ambulance.id)
    if request.args.get('city'):
        statement = statement.where(Ambulance.city == request.args['city'])
    if request.args.get('hospital_id'):
        statement = statement.where(Ambulance.hospital_id == integer(request.args['hospital_id'], 'Hospital'))
    if request.args.get('area'):
        statement = statement.where(Ambulance.area == request.args['area'])
    rows = [a.public() for a in db.session.scalars(statement)]
    if request.args.get('status'):
        value = choice(request.args['status'], ('available', 'busy', 'unknown'), 'Status')
        rows = [row for row in rows if row['status'] == value]
    return success({'ambulances': rows, 'disclaimer': 'Published hospital dispatch contacts. Confirm vehicle availability by phone. No live fleet feed, dispatch or ETA is provided.'})


@bp.get('/api/notifications')
@role_required()
def notifications():
    stmt = db.select(Notification).where(Notification.user_id == g.user.id)
    unread = db.session.scalar(db.select(db.func.count(Notification.id)).where(Notification.user_id == g.user.id, Notification.is_read.is_(False)))
    if query_bool('unread_only'):
        stmt = stmt.where(Notification.is_read.is_(False))
    return success({'notifications': [n.public() for n in db.session.scalars(stmt.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(100))], 'unread_count': unread})


@bp.post('/api/notifications/<int:notification_id>/read')
@role_required()
def read_notification(notification_id):
    notification = db.get_or_404(Notification, notification_id)
    if notification.user_id != g.user.id:
        abort(403)
    notification.is_read = True
    db.session.commit()
    return success(notification.public())
