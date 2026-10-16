"""Account security journeys; optionally repeat against isolated PostgreSQL.

TEST_POSTGRES_URL must point to a disposable test database. Each PostgreSQL test
uses its own schema; no production tables are read or altered.
"""
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from test_admin_notifications import load_module


@pytest.fixture(params=['sqlite', 'postgresql'])
def account_api(request, tmp_path, monkeypatch):
    schema = None
    if request.param == 'postgresql':
        url = os.getenv('TEST_POSTGRES_URL')
        if not url:
            pytest.skip('Set TEST_POSTGRES_URL to run real PostgreSQL journeys')
        control = create_engine(url)
        schema = 'test_' + uuid4().hex
        with control.begin() as connection:
            connection.execute(text(f'CREATE SCHEMA {schema}'))
        engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    else:
        url = f'sqlite:///{tmp_path / "accounts.db"}'
        engine = create_engine(url, connect_args={'check_same_thread': False})
    module = load_module(tmp_path, monkeypatch, DATABASE_URL=url, ADMIN_EMAIL='admin@example.com',
                         ENVIRONMENT='production', FRONTEND_BASE_URL='https://cocegn.example',
                         SMTP_HOST='smtp.example.com', SMTP_FROM_EMAIL='sender@example.com')
    monkeypatch.setattr(module, 'engine', engine)
    monkeypatch.setattr(module, 'SessionLocal', sessionmaker(bind=engine))
    config = Config(str(Path(__file__).resolve().parents[1] / 'alembic.ini'))
    mail = []
    monkeypatch.setattr(module, 'send_verification_email', lambda email, token: mail.append(('verify', token)) or True)
    monkeypatch.setattr(module, 'send_password_reset_email', lambda email, token: mail.append(('reset', token)) or True)
    monkeypatch.setattr(module, 'send_admin_notification', lambda *args: True)
    try:
        with engine.begin() as connection:
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
        with TestClient(module.app, base_url='https://cocegn.example',
                        headers={'Origin': 'https://cocegn.example'}) as client:
            yield module, client, mail
    finally:
        engine.dispose()
        if schema:
            with control.begin() as connection:
                connection.execute(text(f'DROP SCHEMA {schema} CASCADE'))
            control.dispose()


def register(client, email='educator@example.com'):
    response = client.post('/auth/register', json=dict(first_name='Test', last_name='Educator',
        email=email, password='OriginalPassword123!'))
    assert response.status_code == 201, response.text


def test_verification_login_reset_revokes_every_session(account_api):
    module, client, mail = account_api
    register(client)
    credentials = dict(email='educator@example.com', password='OriginalPassword123!')
    assert client.post('/auth/login', json=credentials).status_code == 403
    token = mail[-1][1]
    assert client.post('/auth/verify-email', json={'token': token}).status_code == 200
    assert client.post('/auth/verify-email', json={'token': token}).status_code == 400
    response = client.post('/auth/login', json=credentials)
    assert response.status_code == 200
    cookie = response.headers['set-cookie'].lower()
    assert 'httponly' in cookie and 'secure' in cookie and 'samesite=lax' in cookie
    assert client.get('/member/dashboard').status_code == 200
    assert client.get('/admin/overview').status_code == 403
    old_session = client.cookies.get('ce_session')
    assert client.post('/auth/request-password-reset', json={'email': credentials['email']}).status_code == 200
    reset = {'token': mail[-1][1], 'password': 'ReplacementPassword123!'}
    assert client.post('/auth/reset-password', json=reset).status_code == 200
    assert client.get('/auth/me').status_code == 401
    assert client.post('/auth/reset-password', json=reset).status_code == 400
    assert client.post('/auth/login', json=credentials).status_code == 401
    credentials['password'] = reset['password']
    assert client.post('/auth/login', json=credentials).status_code == 200
    assert client.post('/auth/logout').status_code == 204
    assert client.get('/auth/me').status_code == 401
    with module.SessionLocal() as session:
        assert module.find_session_user(session, old_session) is None


def test_expired_verification_and_resend_privacy(account_api):
    module, client, mail = account_api
    register(client)
    token = mail[-1][1]
    with module.SessionLocal() as session:
        verification = session.query(module.EmailVerificationToken).one()
        verification.expires_at = module.now_utc() - timedelta(seconds=1)
        session.commit()
    assert client.post('/auth/verify-email', json={'token': token}).status_code == 400
    existing = client.post('/auth/request-email-verification', json={'email': 'educator@example.com'})
    unknown = client.post('/auth/request-email-verification', json={'email': 'unknown@example.com'})
    assert existing.status_code == unknown.status_code == 200
    assert existing.json() == unknown.json()
    assert 'email_sent' not in existing.json()
    assert client.post('/auth/verify-email', json={'token': mail[-1][1]}).status_code == 200


def test_configured_administrator_can_use_admin_after_verification(account_api):
    _, client, mail = account_api
    register(client, email='admin@example.com')
    credentials = dict(email='admin@example.com', password='OriginalPassword123!')
    assert client.post('/auth/login', json=credentials).status_code == 403
    assert client.post('/auth/verify-email', json={'token': mail[-1][1]}).status_code == 200
    response = client.post('/auth/login', json=credentials)
    assert response.status_code == 200
    assert response.json()['is_admin'] is True
    assert client.get('/admin/overview').status_code == 200


@pytest.mark.parametrize('endpoint,token_model', [
    ('/auth/request-password-reset', 'PasswordResetToken'),
    ('/auth/request-email-verification', 'EmailVerificationToken'),
])
def test_mail_outage_is_clear_and_does_not_reveal_accounts(account_api, monkeypatch, endpoint, token_model):
    module, client, mail = account_api
    register(client)
    with module.SessionLocal() as session:
        before = session.query(getattr(module, token_model)).count()
    sent_before = len(mail)
    monkeypatch.setattr(module, 'SMTP_HOST', None)
    monkeypatch.setattr(module, 'BREVO_API_KEY', None)
    known = client.post(endpoint, json={'email': 'educator@example.com'})
    unknown = client.post(endpoint, json={'email': 'unknown@example.com'})
    assert known.status_code == unknown.status_code == 503
    assert known.json() == unknown.json()
    assert 'unavailable' in known.json()['detail'].lower()
    assert 'has been sent' not in str(known.json())
    assert len(mail) == sent_before
    with module.SessionLocal() as session:
        assert session.query(getattr(module, token_model)).count() == before


@pytest.mark.parametrize('endpoint,send_function', [
    ('/auth/request-password-reset', 'send_password_reset_email'),
    ('/auth/request-email-verification', 'send_verification_email'),
])
def test_provider_failure_response_preserves_account_privacy(account_api, monkeypatch, endpoint, send_function):
    module, client, _ = account_api
    register(client)
    monkeypatch.setattr(module, send_function, lambda *args: False)
    known = client.post(endpoint, json={'email': 'educator@example.com'})
    unknown = client.post(endpoint, json={'email': 'unknown@example.com'})
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert 'email_sent' not in known.json()
    assert 'has been sent' not in known.json()['message']
