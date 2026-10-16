"""A provider success must never confirm a payment with mismatched details."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select

from test_admin_notifications import load_module, use_temp_database


@pytest.mark.parametrize('changed', [
    {'amount': 9999}, {'currency': 'USD'}, {'reference': 'another-reference'},
])
def test_provider_success_with_mismatch_is_rejected(tmp_path, monkeypatch, changed):
    module = load_module(tmp_path, monkeypatch)
    use_temp_database(module, tmp_path, monkeypatch)
    with module.SessionLocal() as session:
        session.add(module.Payment(reference='test-reference', payment_type='donation',
            email='donor@example.com', amount_kobo=10000, currency='NGN',
            status='pending', created_at=module.now_utc()))
        session.commit()
    transaction = dict(status='success', amount=10000, currency='NGN', reference='test-reference')
    transaction.update(changed)
    monkeypatch.setattr(module, 'paystack_request', lambda path: transaction)

    with pytest.raises(HTTPException) as error:
        module.verify_payment('test-reference')
    assert error.value.status_code == 502
    with module.SessionLocal() as session:
        payment = session.scalar(select(module.Payment))
        assert payment.status == 'pending'
        assert payment.paid_at is None


def test_matching_success_confirms_payment(tmp_path, monkeypatch):
    module = load_module(tmp_path, monkeypatch)
    use_temp_database(module, tmp_path, monkeypatch)
    with module.SessionLocal() as session:
        session.add(module.Payment(reference='test-reference', payment_type='donation',
            email='donor@example.com', amount_kobo=10000, currency='NGN',
            status='pending', created_at=module.now_utc()))
        session.commit()
    monkeypatch.setattr(module, 'paystack_request', lambda path: dict(
        status='success', amount=10000, currency='NGN', reference='test-reference'))
    assert module.verify_payment('test-reference') == {'status': 'success', 'amount_ngn': 100}
    with module.SessionLocal() as session:
        payment = session.scalar(select(module.Payment))
        assert payment.status == 'success'
        assert payment.paid_at is not None
