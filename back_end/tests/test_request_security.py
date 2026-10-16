"""Exercise access controls at the HTTP boundary with a disposable database."""
import pytest
from fastapi.testclient import TestClient
from test_admin_notifications import load_module, use_temp_database


@pytest.fixture
def api(tmp_path, monkeypatch):
    module = load_module(tmp_path, monkeypatch)
    use_temp_database(module, tmp_path, monkeypatch)
    return module, TestClient(module.app)


def test_private_endpoints_reject_anonymous_visitors(api):
    _, client = api
    for path in ['/auth/me', '/member/dashboard', '/admin/overview',
                 '/admin/membership-applications', '/admin/contact-submissions',
                 '/admin/newsletter-subscribers']:
        assert client.get(path).status_code == 401


def test_authenticated_responses_are_never_cached(api):
    _, client = api
    response = client.get('/auth/me')
    assert response.headers['Cache-Control'] == 'no-store'


def test_foreign_origin_cannot_write_with_session_cookie(api):
    _, client = api
    response = client.post('/auth/logout', headers={
        'Origin': 'https://attacker.example', 'Cookie': 'ce_session=any-session'})
    assert response.status_code == 403


def test_login_requests_are_rate_limited(api):
    module, client = api
    # Invalid input must count too, without spending time on expensive hashes.
    statuses = [client.post('/auth/login', json={}).status_code
                for _ in range(11)]
    assert statuses[:10] == [422] * 10
    assert statuses[10] == 429
    assert int(client.post('/auth/login', json={}).headers['Retry-After']) > 0


@pytest.mark.parametrize('configured', [False, True])
def test_mail_failure_logs_never_include_private_data(api, monkeypatch, capsys, configured):
    module, _ = api
    monkeypatch.setattr(module, 'SMTP_HOST', 'smtp.example.com' if configured else None)
    monkeypatch.setattr(module, 'SMTP_FROM_EMAIL', 'sender@example.com' if configured else None)
    def fail(*args, **kwargs):
        raise OSError('Server echoed private@example.com secret-token')
    monkeypatch.setattr(module.smtplib, 'SMTP', fail)
    assert module.send_email('private@example.com', 'Private subject', 'secret-token') is False
    output = capsys.readouterr().out
    assert 'EMAIL NOT SENT' in output
    assert 'private@example.com' not in output
    assert 'secret-token' not in output
    assert 'Private subject' not in output
