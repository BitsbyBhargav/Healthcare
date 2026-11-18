from models import db, Hospital, BedHistory
from services.prediction_service import train_predict, forecast, DISCLAIMER, SYNTHETIC_KAGGLE_DISCLAIMER


def test_prediction_bounded_with_measured_validation(app):
    c=app.test_client()
    result=c.get('/api/predictions?hospital_id=1&bed_type=icu')
    assert result.status_code==200
    f=result.json['data']
    assert isinstance(f['predicted_available'], (float,int))
    assert 0 <= f['predicted_available'] <= f['capacity']
    assert f['disclaimer']==SYNTHETIC_KAGGLE_DISCLAIMER
    assert f['data_source']=='synthetic_kaggle'
    assert f['method']=='RandomForestRegressor'
    assert f['validation_mae'] >= 0 and f['validation_days'] > 0
    assert len(f['history'])==45
    assert c.get('/api/predictions?bed_type=invalid').status_code==400


def test_missing_history_fallback(app):
    with app.app_context():
        db.session.execute(db.delete(BedHistory).where(BedHistory.hospital_id==1))
        db.session.commit()
        f=forecast(db.session.get(Hospital,1),'general')
        assert not f['forecast_available']
        assert f['predicted_available'] is None
        assert f['validation_mae'] is None
        assert f['data_source']=='workspace_unverified'
        assert f['disclaimer']==DISCLAIMER


def test_small_series_fallback():
    from datetime import date, timedelta
    today=date.today()
    result=train_predict(tuple((today-timedelta(days=3-i), i+1) for i in range(3)), today)
    assert result[0]==2 and result[1]=='Moving average fallback'
