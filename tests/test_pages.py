import pytest


@pytest.mark.parametrize('url', ['/', '/hospitals', '/hospitals/1', '/login', '/register', '/ambulances', '/predictions', '/api/health', '/api/ambulances', '/api/dashboard/stats'])
def test_public_pages_and_apis(app, url):
    response=app.test_client().get(url)
    assert response.status_code==200


def test_synthetic_inventory_and_forecast_are_disclosed(app):
    c=app.test_client()
    detail=c.get('/hospitals/1').get_data(as_text=True)
    forecast_page=c.get('/predictions').get_data(as_text=True)
    data=c.get('/api/predictions?hospital_id=1&bed_type=general').json['data']
    assert 'Synthetic demo · not verified' in detail
    assert 'Kaggle sample dataset' in forecast_page
    assert data['data_source']=='synthetic_kaggle'
    assert 'Kaggle-derived synthetic demo data' in data['disclaimer']


def test_authenticated_pages(patient, admin):
    assert patient.get('/patient').status_code==200
    assert patient.get('/admin').status_code==403
    assert admin.get('/admin').status_code==200
    assert admin.get('/patient').status_code==403


def test_ambulance_demo_labels(app):
    c=app.test_client()
    data=c.get('/api/ambulances').json['data']
    assert len(data['ambulances'])>=5
    assert all(a['is_demo'] for a in data['ambulances'])
    assert b'simulated' in c.get('/ambulances').data
    assert b'Demo Data' in c.get('/').data


def test_consistent_errors(app):
    c=app.test_client()
    for url, code in [('/api/hospitals/999',404),('/api/admin/beds',401),('/api/hospitals?bed_type=bad',400)]:
        response=c.get(url)
        assert response.status_code==code
        assert response.json['ok'] is False and response.json['error']['message']
    assert c.get('/no-such-page').status_code==404
