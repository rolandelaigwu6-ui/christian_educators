"""The supplied COCEGN tiers must save with their application details, never guessed fees."""
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_admin_notifications import load_module, use_temp_database


def application(module, tier, **overrides):
    values = dict(tier=tier, first_name='Jane', last_name='Doe', email='jane@example.com',
                  country='Nigeria', role='Teacher', organization='Community school',
                  marketing_consent=True, phone='+2348030000000', location='Benue',
                  church='Community church', faith_agreement=True, terms_accepted=True)
    values.update(overrides)
    return module.MembershipApplicationRequest(**values)


@pytest.mark.parametrize('tier', ['bronze', 'silver', 'gold', 'diamond'])
def test_supplied_tiers_save_even_if_confirmation_email_fails(tmp_path, monkeypatch, tier):
    module = load_module(tmp_path, monkeypatch)
    use_temp_database(module, tmp_path, monkeypatch)
    monkeypatch.setattr(module, 'send_email', lambda *args: False)
    result = module.submit_membership_application(application(module, tier))
    assert result['email_sent'] is False
    with module.SessionLocal() as session:
        saved = session.scalar(select(module.MembershipApplication))
        profile = session.get(module.MembershipApplicationProfile, saved.id)
        assert saved.tier == tier
        assert profile.phone == '+2348030000000'
        assert profile.location == 'Benue'
        assert profile.church == 'Community church'
        assert profile.faith_agreement is True


def test_new_tiers_require_values_agreement(tmp_path, monkeypatch):
    module = load_module(tmp_path, monkeypatch)
    use_temp_database(module, tmp_path, monkeypatch)
    with pytest.raises(HTTPException) as error:
        module.submit_membership_application(application(module, 'bronze', faith_agreement=False))
    assert error.value.status_code == 422
    with module.SessionLocal() as session:
        assert session.scalar(select(module.MembershipApplication)) is None


def test_unconfirmed_membership_prices_cannot_be_charged(tmp_path, monkeypatch):
    module = load_module(tmp_path, monkeypatch)
    monkeypatch.setattr(module, 'PAYMENTS_ENABLED', True)
    for tier in ('bronze', 'diamond', 'coverage'):
        with pytest.raises(HTTPException) as error:
            module.initialize_payment(module.PaymentInitializationRequest(payment_type='membership', email='jane@example.com', tier=tier))
        assert error.value.status_code == 503


def test_updates_are_optional_when_application_terms_are_accepted(tmp_path, monkeypatch):
    module = load_module(tmp_path, monkeypatch)
    use_temp_database(module, tmp_path, monkeypatch)
    monkeypatch.setattr(module, 'send_email', lambda *args: False)
    module.submit_membership_application(application(module, 'silver', marketing_consent=False, terms_accepted=True))
    with module.SessionLocal() as session:
        saved = session.scalar(select(module.MembershipApplication))
        assert saved.marketing_consent is False
        assert session.get(module.MembershipApplicationConsent, saved.id).terms_accepted is True


def test_rejects_missing_application_terms_even_with_updates_opt_in(tmp_path, monkeypatch):
    module = load_module(tmp_path, monkeypatch)
    use_temp_database(module, tmp_path, monkeypatch)
    with pytest.raises(HTTPException) as error:
        module.submit_membership_application(application(module, 'gold', terms_accepted=False))
    assert error.value.status_code == 422


def test_admin_sees_details_but_notification_does_not(tmp_path, monkeypatch):
    module = load_module(tmp_path, monkeypatch)
    use_temp_database(module, tmp_path, monkeypatch)
    sends = []
    monkeypatch.setattr(module, 'send_email', lambda *args: sends.append(args) or True)
    module.submit_membership_application(application(module, 'diamond', terms_accepted=True))
    monkeypatch.setattr(module, 'require_admin', lambda token: None)
    row = module.list_membership_applications('test-session')[0]
    assert row['phone'] == '+2348030000000'
    assert row['location'] == 'Benue'
    assert row['church'] == 'Community church'
    assert row['faith_agreement'] is True
    assert all('Community church' not in body and '+2348030000000' not in body for _, _, body in sends)


def test_new_tiers_need_explicit_application_consent(tmp_path, monkeypatch):
    module = load_module(tmp_path, monkeypatch)
    use_temp_database(module, tmp_path, monkeypatch)
    with pytest.raises(HTTPException) as error:
        module.submit_membership_application(application(module, 'bronze', terms_accepted=None))
    assert error.value.status_code == 422
