"""Admin-notification tests.

Guards three decisions that are easy to undo by accident:

  1. A blank recipient is **reported**. `send_email` returned early on a falsy
     recipient *before* printing anything, so an unset `ADMIN_NOTIFICATION_EMAIL`
     meant no mail, no terminal banner, and no warning on any surface. Completely
     invisible -- the worst possible failure mode for a notification setting.
  2. Every admin notification carries the submitter's **name and email**.
  3. No admin notification carries the submitter's **message text**. Contact
     submissions can hold prayer requests and job disputes; copying that into an
     email would put it in an inbox, outside the database and outside the admin
     login. `send_admin_notification` takes no parameter that could carry it, and
     the signature is the whole safeguard -- so it is asserted directly.

`back_end.py` captures its configuration at import time, so these tests control the
environment and reimport the module (same pattern as test_env_loading.py).

Addresses below use `example.com`, **not** `example.test`. `EmailStr` validates
through email-validator, which rejects special-use TLDs (`.test`, `.invalid`,
`.localhost`, `.onion`) -- a `.test` fixture raises ValidationError before the route
body runs, so the test would fail without exercising anything. Do not "tidy" these
back to `.test`.
"""

import importlib
import sys
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BACK_END_DIR = Path(__file__).resolve().parents[1]
if str(BACK_END_DIR) not in sys.path:
    sys.path.insert(0, str(BACK_END_DIR))

ADMIN = "admin@example.com"

# Settings that could leak in from the ambient environment or a previous reload.
MANAGED_SETTINGS = (
    "SMTP_HOST",
    "SMTP_FROM_EMAIL",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "ADMIN_NOTIFICATION_EMAIL",
)


def load_module(tmp_path, monkeypatch, **settings):
    """Import back_end against a throwaway .env, never the developer's real one."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        "".join(f"{key}={value}\n" for key, value in settings.items()),
        encoding="utf-8",
    )

    for key in MANAGED_SETTINGS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENV_FILE", str(env_file))

    import back_end

    return importlib.reload(back_end)


def use_temp_database(module, tmp_path, monkeypatch):
    """Point the module's SessionLocal at a throwaway database.

    Routes resolve `SessionLocal` as a module global at call time, so replacing the
    attribute is enough. Without this the routes would write to the developer's real
    back_end/christian_educators.db.
    """
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    module.Base.metadata.create_all(engine)
    monkeypatch.setattr(module, "SessionLocal", sessionmaker(bind=engine))


def capture_sends(module, monkeypatch):
    """Record every send instead of performing one."""
    sends = []

    def fake_send_email(recipient, subject, body):
        sends.append((recipient, subject, body))
        return True

    monkeypatch.setattr(module, "send_email", fake_send_email)
    return sends


def admin_sends(sends):
    return [send for send in sends if send[0] == ADMIN]


def test_blank_recipient_is_reported_not_silently_dropped(tmp_path, monkeypatch, capsys):
    """The silent no-op: no recipient used to mean no output of any kind."""
    module = load_module(tmp_path, monkeypatch)

    assert module.send_email(None, "Subject", "Body") is False

    assert "EMAIL NOT SENT" in capsys.readouterr().out


def test_admin_notification_carries_the_name_and_email(tmp_path, monkeypatch):
    module = load_module(tmp_path, monkeypatch, ADMIN_NOTIFICATION_EMAIL=ADMIN)
    sends = capture_sends(module, monkeypatch)

    module.send_admin_notification(
        "New contact message",
        "A new contact message was submitted.",
        "Jane Doe",
        "jane@example.com",
    )

    recipient, _subject, body = sends[0]
    assert recipient == ADMIN
    assert "Jane Doe" in body
    assert "jane@example.com" in body


def test_admin_notification_handles_a_submitter_with_no_name(tmp_path, monkeypatch):
    """Newsletter signup only asks for a first name, and it is optional."""
    module = load_module(tmp_path, monkeypatch, ADMIN_NOTIFICATION_EMAIL=ADMIN)
    sends = capture_sends(module, monkeypatch)

    module.send_admin_notification(
        "New newsletter subscriber",
        "A new newsletter subscription was received.",
        None,
        "jane@example.com",
    )

    body = sends[0][2]
    assert "not given" in body
    assert "jane@example.com" in body


def test_admin_notification_has_no_parameter_for_message_text(tmp_path, monkeypatch):
    """The privacy decision, asserted structurally.

    There is no argument a caller could pass the submitter's message through, so
    adding it later requires deliberately widening this signature.
    """
    import inspect

    module = load_module(tmp_path, monkeypatch)

    parameters = list(inspect.signature(module.send_admin_notification).parameters)

    assert parameters == ["subject", "what_happened", "name", "email"]


def test_registering_an_account_notifies_the_admin(tmp_path, monkeypatch):
    """New accounts used to be invisible to the admin until they opened the dashboard."""
    module = load_module(tmp_path, monkeypatch, ADMIN_NOTIFICATION_EMAIL=ADMIN)
    use_temp_database(module, tmp_path, monkeypatch)
    sends = capture_sends(module, monkeypatch)

    module.register_account(
        module.RegistrationRequest(
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            password="a-sufficiently-long-password",
        )
    )

    notifications = admin_sends(sends)
    assert len(notifications) == 1
    assert "Jane Doe" in notifications[0][2]
    assert "jane@example.com" in notifications[0][2]


def test_contact_notification_omits_the_submitters_message(tmp_path, monkeypatch):
    """Name and email yes; the message body stays behind the admin login."""
    module = load_module(tmp_path, monkeypatch, ADMIN_NOTIFICATION_EMAIL=ADMIN)
    use_temp_database(module, tmp_path, monkeypatch)
    sends = capture_sends(module, monkeypatch)

    module.submit_contact_form(
        module.ContactSubmissionRequest(
            name="Jane Doe",
            email="jane@example.com",
            topic="Prayer request",
            message="Please pray for my situation at St Mary's school.",
        )
    )

    notifications = admin_sends(sends)
    assert len(notifications) == 1
    body = notifications[0][2]
    assert "Jane Doe" in body
    assert "jane@example.com" in body
    assert "St Mary" not in body


def test_membership_and_newsletter_notify_the_admin(tmp_path, monkeypatch):
    module = load_module(tmp_path, monkeypatch, ADMIN_NOTIFICATION_EMAIL=ADMIN)
    use_temp_database(module, tmp_path, monkeypatch)
    sends = capture_sends(module, monkeypatch)

    module.submit_membership_application(
        module.MembershipApplicationRequest(
            tier="coverage",
            first_name="Jane",
            last_name="Doe",
            email="jane@example.com",
            country="Nigeria",
            role="Teacher",
            organization="St Mary's",
            marketing_consent=True,
        )
    )
    module.subscribe_to_newsletter(
        module.NewsletterSubscriptionRequest(
            email="sam@example.com", first_name="Sam"
        )
    )

    bodies = [body for _recipient, _subject, body in admin_sends(sends)]
    assert len(bodies) == 2
    assert any("Jane Doe" in body for body in bodies)
    assert any("Sam" in body for body in bodies)
