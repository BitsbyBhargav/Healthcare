from flask import Blueprint, request
from models import db, Hospital, BED_TYPES
from services.common import success, integer, choice
from services.prediction_service import forecast

bp = Blueprint('predictions', __name__)


@bp.get('/api/predictions')
def predictions():
    hospital_id = integer(request.args.get('hospital_id', 1), 'Hospital')
    bed_type = choice(request.args.get('bed_type', 'general'), BED_TYPES, 'Bed type')
    return success(forecast(db.get_or_404(Hospital, hospital_id), bed_type))
