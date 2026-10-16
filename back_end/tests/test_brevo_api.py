"""HTTPS mail preserves truthful delivery feedback and private failure logs."""
import io
import json
from urllib.error import HTTPError

import pytest
from test_admin_notifications import load_module


def configured(tmp_path, monkeypatch):
    return load_module(tmp_path, monkeypatch, BREVO_API_KEY='test-private-api-key',
                       SMTP_FROM_EMAIL='sender@example.com')


def test_api_delivery_uses_server_side_credentials_and_provider_acknowledgement(tmp_path, monkeypatch):
    module=configured(tmp_path,monkeypatch)
    requests=[]
    def send(request, timeout):
        requests.append(request)
        return io.BytesIO(json.dumps({'messageId':'provider-confirmation'}).encode())
    monkeypatch.setattr(module,'urlopen',send)
    assert module.send_email('recipient@example.com','Subject','Message body') is True
    request=requests[0]
    assert request.full_url=='https://api.brevo.com/v3/smtp/email'
    assert request.get_header('Api-key')=='test-private-api-key'
    payload=json.loads(request.data)
    assert payload['sender']['email']=='sender@example.com'
    assert payload['to']==[{'email':'recipient@example.com'}]
    assert payload['subject']=='Subject' and payload['textContent']=='Message body'
    assert 'test-private-api-key' not in request.data.decode()
    assert module.health_check()['mail_configured'] is True


@pytest.mark.parametrize('response',[{}, {'messageId':''}, ['unexpected'], 'invalid-json'])
def test_api_never_claims_delivery_without_provider_confirmation(tmp_path,monkeypatch,response):
    module=configured(tmp_path,monkeypatch)
    data=response.encode() if isinstance(response,str) else json.dumps(response).encode()
    monkeypatch.setattr(module,'urlopen',lambda *args,**kwargs:io.BytesIO(data))
    assert module.send_email('recipient@example.com','Subject','Body') is False


def test_api_failure_does_not_expose_keys_recipient_or_content(tmp_path,monkeypatch,capsys):
    module=configured(tmp_path,monkeypatch)
    def fail(*args,**kwargs):
        raise HTTPError('https://api.brevo.com/v3/smtp/email',401,
            'recipient@example.com test-private-api-key private-content',{},None)
    monkeypatch.setattr(module,'urlopen',fail)
    assert module.send_email('recipient@example.com','Private subject','private-content') is False
    output=capsys.readouterr().out
    assert 'EMAIL NOT SENT' in output
    for private in ['recipient@example.com','test-private-api-key','private-content','Private subject']:
        assert private not in output
