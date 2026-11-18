import logging
from datetime import timedelta
from functools import lru_cache
from models import db, BedHistory, Bed, now

DISCLAIMER = 'Experimental forecast from unverified workspace history. Not validated for medical decisions.'
SYNTHETIC_KAGGLE_DISCLAIMER = 'Experimental forecast based on Kaggle-derived synthetic demo data. Not validated for medical decisions.'
logger = logging.getLogger(__name__)


def features(day, previous):
    recent = previous[-3:]
    return [day.weekday(), previous[-1], sum(recent) / len(recent), previous[-1] - previous[-2]]


@lru_cache(maxsize=128)
def train_predict(series, next_date):
    values = [row[1] for row in series]
    fallback = sum(values[-3:]) / len(values[-3:]) if values else 0.0
    if len(series) < 14:
        return fallback, 'Moving average fallback', None, None
    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error
        x, y = [], []
        for i in range(3, len(series)):
            x.append(features(series[i][0], values[:i]))
            y.append(values[i])
        split = max(5, int(len(x) * 0.8))
        validation_model = RandomForestRegressor(n_estimators=60, max_depth=5, random_state=42, n_jobs=1)
        validation_model.fit(x[:split], y[:split])
        mae = float(mean_absolute_error(y[split:], validation_model.predict(x[split:])))
        # Refit on all observed days only after the chronological holdout measurement.
        model = RandomForestRegressor(n_estimators=60, max_depth=5, random_state=42, n_jobs=1)
        model.fit(x, y)
        result = float(model.predict([features(next_date, values)])[0])
        return result, 'RandomForestRegressor', round(mae, 2), len(y[split:])
    except Exception:
        logger.exception('Forecast training unavailable; using moving average.')
        return fallback, 'Moving average fallback', None, None


def forecast(hospital, bed_type):
    rows = db.session.scalars(db.select(BedHistory).where(BedHistory.hospital_id == hospital.id,
        BedHistory.bed_type == bed_type, BedHistory.recorded_date <= now().date()).order_by(BedHistory.recorded_date)).all()
    today = now().date()
    series = tuple((r.recorded_date, r.available_beds) for r in rows)
    capacity = db.session.scalar(db.select(db.func.count(Bed.id)).where(Bed.hospital_id == hospital.id, Bed.bed_type == bed_type))
    current = db.session.scalar(db.select(db.func.count(Bed.id)).where(Bed.hospital_id == hospital.id, Bed.bed_type == bed_type, Bed.status == 'available'))
    stale = not rows or rows[-1].recorded_date < today - timedelta(days=1)
    forecast_available = len(rows) >= 7 and not stale
    if not forecast_available:
        value, method, mae, validation_days = None, 'Unavailable: at least seven recent recorded days required', None, None
    else:
        value, method, mae, validation_days = train_predict(series, today + timedelta(days=1))
    sources = {row.source for row in rows}
    data_source = next((source for source in ('synthetic_kaggle', 'synthetic_test') if source in sources), 'workspace_unverified')
    disclaimer = SYNTHETIC_KAGGLE_DISCLAIMER if data_source == 'synthetic_kaggle' else (
        'Experimental forecast based on synthetic test data. Not validated for medical decisions.'
        if data_source == 'synthetic_test' else DISCLAIMER)
    return {
        'hospital_id': hospital.id, 'hospital_name': hospital.name, 'bed_type': bed_type,
        'current_available': current, 'capacity': capacity, 'forecast_available': forecast_available,
        'predicted_available': round(max(0.0, min(float(capacity), value)), 1) if value is not None else None,
        'forecast_date': (today + timedelta(days=1)).isoformat(), 'method': method,
        'validation_mae': mae, 'validation_days': validation_days, 'history_days': len(rows),
        'history': [{'date': r.recorded_date.isoformat(), 'available': r.available_beds, 'capacity': r.total_beds} for r in rows],
        'disclaimer': disclaimer,
        'data_source': data_source,
        'explanation': 'Features use target-day weekday and only earlier days: previous availability, three-day mean and recent change. The final 20% is a chronological validation holdout. The model is then refitted on observed history. No clinical variables are collected.',
    }
