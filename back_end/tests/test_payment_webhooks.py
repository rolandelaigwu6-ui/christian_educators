"""Payment notifications must authenticate raw bytes and settle only once."""
import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from test_admin_notifications import load_module, use_temp_database


@pytest.fixture
def api(tmp_path, monkeypatch):
    module = load_module(tmp_path, monkeypatch, PAYSTACK_SECRET_KEY='sk_test_fixture')
    use_temp_database(module, tmp_path, monkeypatch)
    with module.SessionLocal() as session:
        session.add(module.Payment(reference='test-reference', payment_type='donation',
            email='donor@example.com', amount_kobo=10000, currency='NGN',
            status='pending', created_at=module.now_utc()))
        session.commit()
    return module, TestClient(module.app)


def notify(api, event=None, raw=None, signature=None):
    module, client = api
    body = raw if raw is not None else json.dumps(event).encode()
    signed = signature if signature is not None else hmac.new(
        module.PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512).hexdigest()
    return client.post('/payments/webhook', content=body,
        headers={'Content-Type': 'application/json', 'x-paystack-signature': signed})


def event(**changes):
    data = dict(reference='test-reference', amount=10000, currency='NGN', status='success')
    data.update(changes)
    return {'event': 'charge.success', 'data': data}


def read_payment(module):
    with module.SessionLocal() as session:
        payment = session.scalar(select(module.Payment))
        return payment.status, payment.paid_at


def test_signed_webhook_settles_without_browser_and_is_idempotent(api, monkeypatch):
    module, _ = api
    assert module.PAYMENTS_ENABLED is False
    assert notify(api, event()).status_code == 200
    first = read_payment(module)
    assert first[0] == 'success' and first[1] is not None
    assert notify(api, event()).status_code == 200
    assert read_payment(module) == first
    monkeypatch.setattr(module, 'paystack_request', lambda path: event()['data'])
    assert module.verify_payment('test-reference')['status'] == 'success'
    assert read_payment(module) == first


@pytest.mark.parametrize('signature', ['', 'wrong', '0' * 128])
def test_invalid_signature_cannot_settle(api, signature):
    assert notify(api, event(), signature=signature).status_code == 401
    assert read_payment(api[0]) == ('pending', None)


def test_signature_covers_exact_body(api):
    body = json.dumps(event()).encode()
    signature = hmac.new(api[0].PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512).hexdigest()
    assert notify(api, raw=body+b' ', signature=signature).status_code == 401
    assert read_payment(api[0]) == ('pending', None)


@pytest.mark.parametrize('changes', [
    {'amount': 9999}, {'amount': '10000'}, {'currency': 'USD'}, {'status': 'failed'},
])
def test_signed_mismatched_payment_cannot_settle(api, changes):
    assert notify(api, event(**changes)).status_code == 400
    assert read_payment(api[0]) == ('pending', None)


def test_unknown_payment_and_unhandled_event_are_acknowledged_without_writes(api):
    assert notify(api, event(reference='external-payment')).status_code == 200
    assert notify(api, {'event': 'customer.create', 'data': {}}).status_code == 200
    assert read_payment(api[0]) == ('pending', None)


@pytest.mark.parametrize('raw', [b'not json', b'[]', b'{"event":"charge.success","data":[]}',
    b'{"event":"charge.success","data":{}}'])
def test_signed_malformed_payload_is_rejected(api, raw):
    assert notify(api, raw=raw).status_code == 400
    assert read_payment(api[0]) == ('pending', None)


def test_large_webhook_is_rejected(api):
    assert notify(api, raw=b'x' * (256 * 1024 + 1)).status_code == 413


def test_unconfigured_webhook_is_unavailable(api, monkeypatch):
    module, client = api
    monkeypatch.setattr(module, 'PAYSTACK_SECRET_KEY', None)
    assert client.post('/payments/webhook', content=b'{}').status_code == 503


def test_payment_records_are_private_and_available_to_admin(api, monkeypatch):
    module, client = api
    assert client.get('/admin/payments').status_code == 401
    monkeypatch.setattr(module, 'require_admin', lambda token: None)
    response = client.get('/admin/payments')
    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.json()[0]['reference'] == 'test-reference'
    assert response.json()[0]['amount_ngn'] == 100
    assert response.json()[0]['status'] == 'pending'


@pytest.mark.parametrize('amount', [21474837, 100.5, True])
def test_invalid_amount_never_reaches_provider(api, monkeypatch, amount):
    module, client = api
    monkeypatch.setattr(module, 'PAYMENTS_ENABLED', True)
    def unexpected(*args, **kwargs):
        pytest.fail('Invalid amounts must not reach Paystack')
    monkeypatch.setattr(module, 'paystack_request', unexpected)
    response = client.post('/payments/initialize', json={
        'payment_type': 'donation', 'email': 'donor@example.com', 'donation_amount': amount})
    assert response.status_code == 422


def test_production_refuses_test_key_before_creating_payment(api, monkeypatch):
    module, client = api
    monkeypatch.setattr(module, 'PAYMENTS_ENABLED', True)
    monkeypatch.setattr(module, 'ENVIRONMENT', 'production')
    response = client.post('/payments/initialize', json={
        'payment_type': 'donation', 'email': 'donor@example.com', 'donation_amount': 100})
    assert response.status_code == 503
    with module.SessionLocal() as session:
        assert len(session.scalars(select(module.Payment)).all()) == 1
