from contextlib import asynccontextmanager
from collections import OrderedDict, deque
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import smtplib
from threading import Lock
from time import monotonic
from urllib.parse import urlsplit
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi import Cookie, FastAPI, HTTPException, Request as FastAPIRequest, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field
from pwdlib import PasswordHash
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    create_engine,
    delete,
    select,
    update,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


# Load the .env file before any configuration below is read. Every setting on this
# page is captured at import time, so this must run first.
#
# The path is resolved from this file's location rather than the working directory,
# so the app behaves the same however it is started. ENV_FILE overrides it, which is
# how the tests point at a temporary file instead of a developer's real .env.
#
# load_dotenv does not overwrite variables that are already set, so exporting a value
# in the shell still overrides the file.
load_dotenv(os.getenv("ENV_FILE") or Path(__file__).with_name(".env"))


# Defaults to a SQLite file resolved relative to the working directory, so starting the
# app from a different directory opens a different database. Fine locally; set
# DATABASE_URL in the environment for anything real.
#
# Production uses PostgreSQL via Psycopg; run Alembic migrations before startup.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./christian_educators.db")
# Hosted providers commonly supply a URL without an explicit Python driver.
# Preserve its encoded credentials and TLS query while selecting installed Psycopg.
if DATABASE_URL.startswith(("postgres://", "postgresql://")):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL.split("://", 1)[1]
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://127.0.0.1:5500")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
ADMIN_NOTIFICATION_EMAIL = os.getenv("ADMIN_NOTIFICATION_EMAIL")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
PAYMENTS_ENABLED = os.getenv("PAYMENTS_ENABLED", "false").lower() == "true"


def engine_options(database_url: str) -> dict:
    """Connect arguments to hand to `create_engine` for `database_url`.

    `check_same_thread` is a SQLite-only argument. By default SQLite refuses to let a
    connection be used from any thread but the one that created it, and FastAPI runs
    synchronous route bodies in a threadpool -- so for SQLite it has to be relaxed.
    Every other driver rejects the argument outright with a TypeError, which would turn
    a configuration change into a startup crash.

    Kept separate from the call below so the rule can be tested without installing a
    driver for the non-SQLite case.
    """
    if database_url.startswith("sqlite"):
        return {"connect_args": {"check_same_thread": False}}
    return {}


engine = create_engine(DATABASE_URL, **engine_options(DATABASE_URL))

SessionLocal = sessionmaker(bind=engine)
password_hash = PasswordHash.recommended()

SESSION_COOKIE_NAME = "ce_session"
SESSION_DURATION = timedelta(days=7)
COOKIE_SECURE = ENVIRONMENT == "production"
DUMMY_PASSWORD_HASH = password_hash.hash(
    "this-is-not-a-real-user-password"
)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class UserSession(Base):
    __tablename__ = "user_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id"),
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True)
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


class MembershipApplication(Base):
    __tablename__ = "membership_applications"

    id: Mapped[int] = mapped_column(primary_key=True)
    tier: Mapped[str] = mapped_column(String(30))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), index=True)
    country: Mapped[str] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(String(100), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)
    marketing_consent: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class MembershipApplicationProfile(Base):
    # A companion table keeps existing applications intact without adding columns
    # to their table. Alembic creates it on fresh and compatible existing databases.
    __tablename__ = "membership_application_profiles"

    application_id: Mapped[int] = mapped_column(ForeignKey("membership_applications.id"), primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    location: Mapped[str | None] = mapped_column(String(150), nullable=True)
    church: Mapped[str | None] = mapped_column(String(255), nullable=True)
    faith_agreement: Mapped[bool] = mapped_column(Boolean, default=False)


class MembershipApplicationConsent(Base):
    # Consent is recorded separately so rolling out the optional-updates control
    # does not alter existing profile rows or infer consent for older applications.
    __tablename__ = "membership_application_consents"

    application_id: Mapped[int] = mapped_column(ForeignKey("membership_applications.id"), primary_key=True)
    terms_accepted: Mapped[bool] = mapped_column(Boolean)


class ContactSubmission(Base):
    __tablename__ = "contact_submissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(255), index=True)
    topic: Mapped[str | None] = mapped_column(String(150), nullable=True)
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class NewsletterSubscriber(Base):
    __tablename__ = "newsletter_subscribers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    subscribed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    payment_type: Mapped[str] = mapped_column(String(30))
    email: Mapped[str] = mapped_column(String(255), index=True)
    amount_kobo: Mapped[int] = mapped_column()
    currency: Mapped[str] = mapped_column(String(3), default="NGN")
    status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RegistrationRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)


class RegistrationResponse(BaseModel):
    id: int
    first_name: str
    email: EmailStr
    email_verified: bool
    # False means the account was created but the verification email could not be
    # sent, so the client must not tell the user to go and check their inbox.
    email_sent: bool


class EmailRequest(BaseModel):
    email: EmailStr


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=32, max_length=255)


class PasswordResetRequest(BaseModel):
    token: str = Field(min_length=32, max_length=255)
    password: str = Field(min_length=12, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class ProfileUpdateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)


class CurrentUserResponse(BaseModel):
    id: int
    first_name: str
    email: EmailStr
    email_verified: bool
    is_admin: bool


class MemberDashboardResponse(CurrentUserResponse):
    greeting: str
    membership_status: str


class MembershipApplicationRequest(BaseModel):
    tier: str = Field(min_length=1, max_length=30)
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    country: str = Field(min_length=1, max_length=100)
    role: str | None = Field(default=None, max_length=100)
    organization: str | None = Field(default=None, max_length=255)
    marketing_consent: bool
    phone: str | None = Field(default=None, max_length=40)
    location: str | None = Field(default=None, max_length=150)
    church: str | None = Field(default=None, max_length=255)
    faith_agreement: bool = False
    terms_accepted: bool | None = None


class ContactSubmissionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    topic: str | None = Field(default=None, max_length=150)
    message: str = Field(min_length=10, max_length=5000)


class NewsletterSubscriptionRequest(BaseModel):
    email: EmailStr
    first_name: str | None = Field(default=None, max_length=100)


class GrantAdminRequest(BaseModel):
    email: EmailStr


class PaymentInitializationRequest(BaseModel):
    payment_type: str = Field(pattern="^(membership|donation)$")
    email: EmailStr
    tier: str | None = Field(default=None, max_length=30)
    # Kobo is stored in PostgreSQL's signed 32-bit integer column.
    donation_amount: int | None = Field(default=None, ge=100, le=21474836, strict=True)


def now_utc():
    return datetime.now(timezone.utc)


def hash_token(token: str):
    return hashlib.sha256(token.encode()).hexdigest()


def create_verification_token(session, user_id: int):
    # A newer verification request invalidates older unused links.
    session.execute(
        delete(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.used_at.is_(None),
        )
    )

    raw_token = secrets.token_urlsafe(32)

    verification_token = EmailVerificationToken(
        user_id=user_id,
        token_hash=hash_token(raw_token),
        expires_at=now_utc() + timedelta(hours=1),
    )

    session.add(verification_token)
    session.commit()

    return raw_token


def send_verification_email(email: str, token: str) -> bool:
    """Email a verification link. Returns True only when it was actually sent."""
    verification_url = f"{FRONTEND_BASE_URL}/pages/verify-email.html?token={token}"
    return send_email(
        email,
        "Verify your Christian Educators account",
        (
            "Welcome to Core Christian Educators Global Network.\n\n"
            "Verify your email address by opening this link within one hour:\n"
            f"{verification_url}\n\n"
            "If you did not create this account, you can ignore this email."
        ),
    )


def send_password_reset_email(email: str, token: str) -> bool:
    """Email a password-reset link. Returns True only when it was actually sent."""
    reset_url = f"{FRONTEND_BASE_URL}/pages/reset-password.html?token={token}"
    return send_email(
        email,
        "Reset your Christian Educators password",
        (
            "A password reset was requested for your Christian Educators account.\n\n"
            "Choose a new password by opening this link within one hour:\n"
            f"{reset_url}\n\n"
            "If you did not request this, you can ignore this email."
        ),
    )


def send_email(recipient: str | None, subject: str, body: str):
    """Send through Brevo HTTPS or SMTP; True requires provider acknowledgement.

    Failures log only a category, never recipients, subjects, bodies, tokens or
    provider error text. A caller must check the result before promising delivery.

    This function deliberately does not raise. A mail outage must not fail a request
    whose data has already been stored; making the failure visible is the caller's job.
    """
    if not recipient:
        # A blank recipient is a configuration mistake, not a delivery failure, and
        # it is otherwise completely invisible -- no mail, no banner, no warning on
        # any surface. Say so, so a blank ADMIN_NOTIFICATION_EMAIL is noticed rather
        # than silently dropping every notification forever.
        print("\n=== EMAIL NOT SENT: no recipient address ===")
        print("Set ADMIN_NOTIFICATION_EMAIL in back_end/.env if this was an admin notice.")
        print("=== end of unsent email ===\n")
        return False

    if BREVO_API_KEY:
        if not SMTP_FROM_EMAIL:
            print('=== EMAIL NOT SENT: verified sender is not configured ===')
            return False
        payload = {
            'sender': {'name': 'Core Christian Educators Global Network', 'email': SMTP_FROM_EMAIL},
            'to': [{'email': recipient}], 'subject': subject, 'textContent': body,
        }
        request = Request('https://api.brevo.com/v3/smtp/email', method='POST',
            data=json.dumps(payload).encode(),
            headers={'api-key': BREVO_API_KEY, 'Content-Type': 'application/json', 'Accept': 'application/json'})
        try:
            with urlopen(request, timeout=15) as response:
                result = json.loads(response.read(1024 * 1024))
            if isinstance(result, dict) and result.get('messageId'):
                return True
            print('=== EMAIL NOT SENT: provider acknowledgement missing ===')
        except (OSError, HTTPError, URLError, ValueError) as error:
            print('=== EMAIL NOT SENT: Brevo API delivery failed ===')
            print(f'Failure category: {type(error).__name__}')
        # Do not retry through SMTP: an ambiguous result could cause duplicates.
        return False

    if not SMTP_HOST or not SMTP_FROM_EMAIL:
        missing = [
            name
            for name, value in (
                ("SMTP_HOST", SMTP_HOST),
                ("SMTP_FROM_EMAIL", SMTP_FROM_EMAIL),
            )
            if not value
        ]
        print("\n=== EMAIL NOT SENT: SMTP is not configured ===")
        print(f"Missing setting(s): {', '.join(missing)}")
        print("Add them to back_end/.env. Until then no mail reaches a real inbox.")
        print("=== end of unsent email ===\n")
        return False

    message = EmailMessage()
    message["From"] = SMTP_FROM_EMAIL
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as smtp:
            if SMTP_USE_TLS:
                smtp.starttls()
            if SMTP_USERNAME and SMTP_PASSWORD:
                smtp.login(SMTP_USERNAME, SMTP_PASSWORD)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException) as error:
        # Form data remains saved even if a provider is temporarily unavailable.
        # Printed as a distinct banner because this is the message that explains a
        # user's "I never got the email" report -- "535 5.7.8 Authentication failed"
        # here means the SMTP key or login is wrong, not that the code is broken.
        print("\n=== EMAIL NOT SENT: delivery failed ===")
        print(f"Failure category: {type(error).__name__}")
        print("=== end of email failure ===\n")
        return False


def send_admin_notification(
    subject: str, what_happened: str, name: str | None, email: str
) -> bool:
    """Tell the admin address that something was submitted.

    Carries the submitter's name and email, and deliberately NOT the body of their
    message. A contact submission can hold a prayer request or a job dispute; an
    email copy would put that text in an inbox, outside the database and outside the
    admin login. The detail stays behind /admin/... -- this message is a nudge to go
    and look, not a copy of the record.

    There is deliberately no parameter for message text, so a caller cannot leak it
    by accident. Adding one would be a privacy decision, not a convenience.

    Every caller discards the return value: whether our internal notification failed
    is not the submitter's business.
    """
    return send_email(
        ADMIN_NOTIFICATION_EMAIL,
        subject,
        (
            f"{what_happened}\n\n"
            f"Name:  {name.strip() if name else '(not given)'}\n"
            f"Email: {email}\n\n"
            "Review it in the admin dashboard."
        ),
    )


def paystack_request(path: str, method: str = "GET", payload=None):
    if not PAYSTACK_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payments are not configured yet.",
        )

    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"https://api.paystack.co{path}",
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode())
    except HTTPError as error:
        print(f"Paystack API rejected the request: HTTP {error.code}")
        if error.code in {401, 403}:
            message = "Paystack rejected the configured secret key. Check that you used a Test Secret Key beginning with sk_test_."
        else:
            message = "Paystack rejected this payment request. Check the backend terminal for the HTTP status."
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=message,
        ) from error
    except (URLError, TimeoutError) as error:
        print(f"Paystack connection failed: {error}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to connect to the payment service. Please try again.",
        ) from error

    if not result.get("status"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The payment service could not create a checkout session.",
        )
    return result["data"]


def create_session_token(session, user_id: int):
    raw_token = secrets.token_urlsafe(32)

    user_session = UserSession(
        user_id=user_id,
        token_hash=hash_token(raw_token),
        expires_at=now_utc() + SESSION_DURATION,
    )

    session.add(user_session)
    session.commit()

    return raw_token


def create_password_reset_token(session, user_id: int):
    session.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
        )
    )
    raw_token = secrets.token_urlsafe(32)
    session.add(
        PasswordResetToken(
            user_id=user_id,
            token_hash=hash_token(raw_token),
            expires_at=now_utc() + timedelta(hours=1),
        )
    )
    session.commit()
    return raw_token


def find_session_user(session, raw_token: str):
    user_session = session.scalar(
        select(UserSession).where(
            UserSession.token_hash == hash_token(raw_token)
        )
    )

    if not user_session or user_session.revoked_at:
        return None

    expires_at = user_session.expires_at

    # SQLite can return timezone-naive dates during local development.
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= now_utc():
        return None

    return session.get(User, user_session.user_id)


def require_admin(ce_session: str | None):
    if not ce_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You must sign in to access the admin dashboard.",
        )

    with SessionLocal() as session:
        user = find_session_user(session, ce_session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your session is missing or has expired.",
            )
        if not user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have administrator access.",
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migrations are a deliberate deployment step, never an implicit alteration
    # during an API worker startup. This works with PostgreSQL and local SQLite.
    config = Config(str(Path(__file__).with_name("alembic.ini")))
    expected = set(ScriptDirectory.from_config(config).get_heads())
    with engine.connect() as connection:
        current = set(MigrationContext.configure(connection).get_current_heads())
    if current != expected:
        raise RuntimeError("Database migrations are required: run alembic -c back_end/alembic.ini upgrade head before starting the API.")
    with SessionLocal() as session:
        admin_email = os.getenv("ADMIN_EMAIL", "").strip().lower()
        if admin_email:
            admin_user = session.scalar(
                select(User).where(User.email == admin_email)
            )
            if admin_user and not admin_user.is_admin:
                admin_user.is_admin = True
                session.commit()
    yield


app = FastAPI(
    title="Christian Educators API",
    version="0.1.0",
    lifespan=lifespan,
)

# Development accepts local servers. Production permits only the configured
# frontend address; the API should normally be served behind the same HTTPS
# domain or a trusted reverse proxy.
cors_origins = [FRONTEND_BASE_URL.rstrip("/")] if ENVIRONMENT == "production" else ["null"]
cors_origin_regex = None if ENVIRONMENT == "production" else r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=cors_origin_regex,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class RequestLimiter:
    """Bounded per-process protection; a multi-worker host also needs edge limits.

    Use the ASGI client address only. Never trust arbitrary forwarded-IP headers;
    configure the proxy/server's trusted forwarding addresses at deployment.
    """
    def __init__(self):
        self.buckets = OrderedDict()
        self.lock = Lock()

    def retry_after(self, key, limit):
        now = monotonic()
        with self.lock:
            while self.buckets and next(iter(self.buckets.values()))[-1] <= now - 60:
                self.buckets.popitem(last=False)
            if key not in self.buckets:
                if len(self.buckets) >= 10000:
                    return 60
                self.buckets[key] = deque()
            attempts = self.buckets[key]
            while attempts and attempts[0] <= now - 60:
                attempts.popleft()
            if len(attempts) >= limit:
                return max(1, int(60 - (now - attempts[0])) + 1)
            attempts.append(now)
            self.buckets.move_to_end(key)
            return 0


request_limiter = RequestLimiter()
REQUEST_LIMITS = {
    "/auth/login": 10, "/auth/register": 5,
    "/auth/request-email-verification": 5, "/auth/request-password-reset": 5,
    "/auth/verify-email": 10, "/auth/reset-password": 10,
    "/membership-applications": 20, "/contact-submissions": 20,
    "/newsletter-subscriptions": 20, "/payments/initialize": 10,
}


def permitted_origin(origin: str) -> bool:
    if origin == FRONTEND_BASE_URL.rstrip("/"):
        return True
    if ENVIRONMENT == "production":
        return False
    try:
        parsed = urlsplit(origin)
        return parsed.scheme in {"http", "https"} and parsed.hostname in {"localhost", "127.0.0.1"}
    except ValueError:
        return False


@app.middleware("http")
async def add_security_headers(request: FastAPIRequest, call_next):
    response = None
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if request.cookies.get(SESSION_COOKIE_NAME) and (
            (origin is not None and not permitted_origin(origin))
            or (origin is None and ENVIRONMENT == "production")
            or request.headers.get("sec-fetch-site") == "cross-site"
        ):
            response = JSONResponse(status_code=403, content={"detail": "This request origin is not permitted."})
        limit = REQUEST_LIMITS.get(request.url.path)
        if response is None and limit:
            address = request.client.host if request.client else "unknown"
            retry = request_limiter.retry_after((address, request.url.path), limit)
            if retry:
                response = JSONResponse(status_code=429,
                    content={"detail": "Too many requests. Please try again shortly."},
                    headers={"Retry-After": str(retry)})
    if response is None:
        response = await call_next(request)
    if request.url.path.startswith(("/auth/", "/member/", "/admin/", "/payments/")):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def mail_is_configured():
    return bool(SMTP_FROM_EMAIL and (BREVO_API_KEY or SMTP_HOST))


def require_mail_configuration():
    # A deployment-wide outage is safe to report identically for every address.
    # Do this before account lookup or token creation, preserving existing links.
    if not mail_is_configured():
        raise HTTPException(status_code=503,
            detail="Email delivery is currently unavailable. Please contact COCEGN or try again later.")


@app.get("/health")
def health_check():
    # mail_configured is a global signal, identical for every caller, so it is safe
    # to expose. It reports configuration presence, not provider/inbox delivery.
    # Unknown-email endpoints must not expose per-request sending outcomes.
    return {
        "status": "ok",
        "mail_configured": mail_is_configured(),
        "payments_configured": bool(PAYSTACK_SECRET_KEY),
        "payments_enabled": PAYMENTS_ENABLED,
    }


@app.post("/payments/initialize")
def initialize_payment(details: PaymentInitializationRequest):
    if not PAYMENTS_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Online payments are temporarily unavailable.",
        )
    if not PAYSTACK_SECRET_KEY or (
        ENVIRONMENT == "production" and not PAYSTACK_SECRET_KEY.startswith("sk_live_")
    ):
        raise HTTPException(status_code=503, detail="Online payments are not ready yet.")

    email = str(details.email).lower()

    if details.payment_type == "membership":
        # COCEGN supplied tier names, but has not approved fees. Never charge the
        # old sample prices, even if donation checkout is enabled later.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Membership fees are awaiting confirmation. Please contact COCEGN.",
        )
    else:
        if not details.donation_amount:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Enter a donation amount of at least ₦100.",
            )
        amount_ngn = details.donation_amount

    reference = f"ce-{details.payment_type}-{secrets.token_hex(16)}"
    payment = Payment(
        reference=reference,
        payment_type=details.payment_type,
        email=email,
        amount_kobo=amount_ngn * 100,
        currency="NGN",
        status="pending",
        created_at=now_utc(),
    )

    with SessionLocal() as session:
        session.add(payment)
        session.commit()

    try:
        checkout = paystack_request(
            "/transaction/initialize",
            method="POST",
            payload={
                "email": email,
                "amount": str(amount_ngn * 100),
                "currency": "NGN",
                "reference": reference,
                "callback_url": f"{FRONTEND_BASE_URL}/pages/payment-result.html",
                "metadata": {
                    "payment_type": details.payment_type,
                    "tier": details.tier,
                },
            },
        )
    except HTTPException:
        with SessionLocal() as session:
            stored_payment = session.scalar(
                select(Payment).where(Payment.reference == reference)
            )
            if stored_payment:
                stored_payment.status = "initialization_failed"
                session.commit()
        raise

    return {"checkout_url": checkout["authorization_url"], "reference": reference}


def record_successful_payment(transaction: dict):
    """Validate a known transaction and atomically preserve its first settlement."""
    reference = transaction.get("reference")
    with SessionLocal() as session:
        payment = session.scalar(select(Payment).where(Payment.reference == reference))
        if payment is None:
            return None
        if (
            transaction.get("status") != "success"
            or type(transaction.get("amount")) is not int
            or transaction["amount"] != payment.amount_kobo
            or transaction.get("currency") != payment.currency
        ):
            raise HTTPException(status_code=502,
                detail="The payment details could not be confirmed. Please contact COCEGN before trying again.")
        amount_ngn = payment.amount_kobo // 100
        session.execute(update(Payment).where(
            Payment.id == payment.id, Payment.status != "success"
        ).values(status="success", paid_at=now_utc()))
        session.commit()
        return amount_ngn


@app.post("/payments/webhook")
async def receive_payment_webhook(request: FastAPIRequest):
    # Keep accepting settlement notifications when new checkout is switched off.
    if not PAYSTACK_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Payments are not configured yet.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 256 * 1024:
            raise HTTPException(status_code=413, detail="Payment notification is too large.")
    signature = request.headers.get("x-paystack-signature", "")
    expected = hmac.new(PAYSTACK_SECRET_KEY.encode(), body, hashlib.sha512).hexdigest()
    if (len(signature) != 128 or not signature.isascii()
        or not hmac.compare_digest(expected, signature)):
        raise HTTPException(status_code=401, detail="Invalid payment notification signature.")
    try:
        event = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid payment notification.")
    if not isinstance(event, dict):
        raise HTTPException(status_code=400, detail="Invalid payment notification.")
    if event.get("event") != "charge.success":
        return {"received": True}
    transaction = event.get("data")
    if (not isinstance(transaction, dict)
        or not isinstance(transaction.get("reference"), str)
        or not 1 <= len(transaction["reference"]) <= 100):
        raise HTTPException(status_code=400, detail="Invalid payment notification.")
    try:
        # No mail or external requests: commit before acknowledging so failures retry.
        await run_in_threadpool(record_successful_payment, transaction)
    except HTTPException as error:
        raise HTTPException(status_code=400, detail=error.detail) from error
    # Other Paystack products can share the account; unknown references create no rows.
    return {"received": True}


@app.get("/payments/verify/{reference}")
def verify_payment(reference: str):
    with SessionLocal() as session:
        payment = session.scalar(select(Payment).where(Payment.reference == reference))
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")

    transaction = paystack_request(f"/transaction/verify/{reference}")
    if transaction.get("status") == "success" and (
        transaction.get("reference") != reference
        or transaction.get("amount") != payment.amount_kobo
        or transaction.get("currency") != payment.currency
    ):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The payment details could not be confirmed. Please contact COCEGN before trying again.")
    if transaction.get("status") == "success":
        amount_ngn = record_successful_payment(transaction)
        return {"status": "success", "amount_ngn": amount_ngn}

    return {"status": transaction.get("status", "pending")}


@app.get("/admin/payments")
def list_payments(ce_session: str | None = Cookie(default=None)):
    require_admin(ce_session)
    with SessionLocal() as session:
        payments = session.scalars(select(Payment).order_by(Payment.id.desc()).limit(100)).all()
        return [{
            "reference": payment.reference,
            "email": payment.email,
            "payment_type": payment.payment_type,
            "amount_ngn": payment.amount_kobo / 100,
            "currency": payment.currency,
            "status": payment.status,
            "created_at": payment.created_at,
            "paid_at": payment.paid_at,
        } for payment in payments]


@app.get("/admin/overview")
def get_admin_overview(ce_session: str | None = Cookie(default=None)):
    require_admin(ce_session)

    with SessionLocal() as session:
        return {
            "membership_applications": len(
                session.scalars(select(MembershipApplication.id)).all()
            ),
            "contact_submissions": len(
                session.scalars(select(ContactSubmission.id)).all()
            ),
            "newsletter_subscribers": len(
                session.scalars(select(NewsletterSubscriber.id)).all()
            ),
        }


@app.get("/admin/membership-applications")
def list_membership_applications(
    ce_session: str | None = Cookie(default=None),
):
    require_admin(ce_session)

    with SessionLocal() as session:
        applications = session.scalars(
            select(MembershipApplication)
            .order_by(MembershipApplication.id.desc())
            .limit(100)
        ).all()
        profiles = {
            profile.application_id: profile
            for profile in session.scalars(select(MembershipApplicationProfile).where(
                MembershipApplicationProfile.application_id.in_([item.id for item in applications])
            )).all()
        }
        consents = {
            consent.application_id: consent
            for consent in session.scalars(select(MembershipApplicationConsent).where(
                MembershipApplicationConsent.application_id.in_([item.id for item in applications])
            )).all()
        }
        return [
            {
                "id": item.id,
                "name": f"{item.first_name} {item.last_name}",
                "phone": profiles[item.id].phone if item.id in profiles else None,
                "location": profiles[item.id].location if item.id in profiles else None,
                "church": profiles[item.id].church if item.id in profiles else None,
                "faith_agreement": profiles[item.id].faith_agreement if item.id in profiles else None,
                "terms_accepted": consents[item.id].terms_accepted if item.id in consents else None,
                "marketing_consent": item.marketing_consent,
                "email": item.email,
                "tier": item.tier,
                "country": item.country,
                "role": item.role,
                "organization": item.organization,
                "created_at": item.created_at,
            }
            for item in applications
        ]


@app.get("/admin/contact-submissions")
def list_contact_submissions(
    ce_session: str | None = Cookie(default=None),
):
    require_admin(ce_session)

    with SessionLocal() as session:
        submissions = session.scalars(
            select(ContactSubmission)
            .order_by(ContactSubmission.id.desc())
            .limit(100)
        ).all()
        return [
            {
                "id": item.id,
                "name": item.name,
                "email": item.email,
                "topic": item.topic,
                "message": item.message,
                "created_at": item.created_at,
            }
            for item in submissions
        ]


@app.get("/admin/newsletter-subscribers")
def list_newsletter_subscribers(
    ce_session: str | None = Cookie(default=None),
):
    require_admin(ce_session)

    with SessionLocal() as session:
        subscribers = session.scalars(
            select(NewsletterSubscriber)
            .order_by(NewsletterSubscriber.id.desc())
            .limit(100)
        ).all()
        return [
            {
                "id": item.id,
                "first_name": item.first_name,
                "email": item.email,
                "subscribed_at": item.subscribed_at,
            }
            for item in subscribers
        ]


@app.post("/admin/users/grant-admin")
def grant_administrator_access(
    details: GrantAdminRequest,
    ce_session: str | None = Cookie(default=None),
):
    require_admin(ce_session)
    email = str(details.email).lower()

    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account was found with that email address.",
            )

        if user.is_admin:
            return {"message": "This user already has administrator access."}

        user.is_admin = True
        session.commit()

    return {"message": "Administrator access granted."}


@app.post("/membership-applications", status_code=status.HTTP_201_CREATED)
def submit_membership_application(details: MembershipApplicationRequest):
    # Keep legacy submissions compatible; only the supplied tiers are offered in
    # the public UI. Existing applications are not relabelled or re-priced.
    supplied_tiers = {"bronze", "silver", "gold", "diamond"}
    allowed_tiers = supplied_tiers | {"basic", "coverage", "student", "retired", "gift", "unsure"}
    email = str(details.email).lower()

    if details.tier not in allowed_tiers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Select a valid membership option.",
        )

    if details.tier in supplied_tiers and not details.faith_agreement:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Please confirm that you support COCEGN's mission and Biblical values.",
        )

    # Old clients used a combined checkbox. New clients separate application
    # consent from optional news, without changing already-saved applications.
    terms_accepted = (
        details.terms_accepted if details.terms_accepted is not None
        else details.marketing_consent if details.tier not in supplied_tiers
        else False
    )
    if not terms_accepted:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="You must accept the Terms of Use and Privacy Policy.",
        )

    with SessionLocal() as session:
        application = MembershipApplication(
            tier=details.tier,
            first_name=details.first_name.strip(),
            last_name=details.last_name.strip(),
            email=email,
            country=details.country.strip(),
            role=details.role.strip() if details.role else None,
            organization=(
                details.organization.strip() if details.organization else None
            ),
            marketing_consent=details.marketing_consent,
            created_at=now_utc(),
        )
        session.add(application)
        session.flush()
        session.add(MembershipApplicationProfile(
            application_id=application.id,
            phone=details.phone.strip() if details.phone else None,
            location=details.location.strip() if details.location else None,
            church=details.church.strip() if details.church else None,
            faith_agreement=details.faith_agreement,
        ))
        session.add(MembershipApplicationConsent(
            application_id=application.id,
            terms_accepted=terms_accepted,
        ))
        session.commit()

    # email_sent reports the submitter's confirmation copy. The admin notification is
    # internal and its failure is not the applicant's concern.
    email_sent = send_email(
        email,
        "We received your membership application",
        (
            "Thank you for applying to Core Christian Educators Global Network. "
            "Our member-care team will review your application and contact you about next steps."
        ),
    )
    send_admin_notification(
        "New membership application",
        "A new membership application was submitted.",
        f"{details.first_name} {details.last_name}",
        email,
    )
    return {
        "message": "Your membership application has been received.",
        "email_sent": email_sent,
    }


@app.post("/contact-submissions", status_code=status.HTTP_201_CREATED)
def submit_contact_form(details: ContactSubmissionRequest):
    email = str(details.email).lower()

    with SessionLocal() as session:
        submission = ContactSubmission(
            name=details.name.strip(),
            email=email,
            topic=details.topic.strip() if details.topic else None,
            message=details.message.strip(),
            created_at=now_utc(),
        )
        session.add(submission)
        session.commit()

    email_sent = send_email(
        email,
        "We received your message",
        "Thank you for contacting Core Christian Educators Global Network. Our team will read your message and follow up with you.",
    )
    send_admin_notification(
        "New contact message",
        "A new contact message was submitted.",
        details.name,
        email,
    )
    return {
        "message": "Your message has been received.",
        "email_sent": email_sent,
    }


@app.post("/newsletter-subscriptions", status_code=status.HTTP_201_CREATED)
def subscribe_to_newsletter(details: NewsletterSubscriptionRequest):
    email = str(details.email).lower()

    with SessionLocal() as session:
        existing_subscriber = session.scalar(
            select(NewsletterSubscriber).where(
                NewsletterSubscriber.email == email
            )
        )

        if existing_subscriber:
            # No mail is sent on the repeat path; reported explicitly so clients can
            # rely on the field always being present.
            return {
                "message": "This email is already subscribed.",
                "email_sent": False,
            }

        subscriber = NewsletterSubscriber(
            email=email,
            first_name=details.first_name.strip() if details.first_name else None,
            subscribed_at=now_utc(),
        )
        session.add(subscriber)
        session.commit()

    email_sent = send_email(
        email,
        "Welcome to the Christian Educators newsletter",
        "You are now subscribed to receive encouragement and updates from Core Christian Educators Global Network.",
    )
    send_admin_notification(
        "New newsletter subscriber",
        "A new newsletter subscription was received.",
        details.first_name,
        email,
    )
    return {
        "message": "You are subscribed to the newsletter.",
        "email_sent": email_sent,
    }


@app.post(
    "/auth/register",
    response_model=RegistrationResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_account(details: RegistrationRequest):
    email = str(details.email).lower()

    with SessionLocal() as session:
        existing_user = session.scalar(
            select(User).where(User.email == email)
        )

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

        user = User(
            first_name=details.first_name.strip(),
            last_name=details.last_name.strip(),
            email=email,
            password_hash=password_hash.hash(details.password),
        )

        session.add(user)
        session.commit()
        session.refresh(user)

        token = create_verification_token(session, user.id)
        email_sent = send_verification_email(user.email, token)

        # The admin is told an account was created; previously a registration was
        # invisible until someone opened the dashboard. Best-effort like every other
        # send -- the account exists either way.
        #
        # Caveat: there is no rate limiting on this route, so registrations can be
        # scripted to generate one admin email each. See Agent.md, known debt.
        send_admin_notification(
            "New account registered",
            "A new account was registered.",
            f"{user.first_name} {user.last_name}",
            user.email,
        )

        # The account is saved either way. Sending email is best-effort, but the
        # client must be told when it failed rather than being told to check an
        # inbox that will never receive anything.
        return {
            "id": user.id,
            "first_name": user.first_name,
            "email": user.email,
            "email_verified": user.email_verified,
            "email_sent": email_sent,
        }


@app.post("/auth/request-email-verification")
def request_email_verification(details: EmailRequest):
    require_mail_configuration()
    email = str(details.email).lower()

    with SessionLocal() as session:
        user = session.scalar(
            select(User).where(User.email == email)
        )

        if user and not user.email_verified:
            token = create_verification_token(session, user.id)
            # Return value deliberately unused: this response must stay identical
            # whether or not the account exists, or it would leak which addresses
            # are registered.
            send_verification_email(user.email, token)

    # Same response whether the email exists or not.
    return {
        "message": (
            "If an account needs verification, a verification email was requested. "
            "If it does not arrive, please contact COCEGN."
        )
    }


@app.post("/auth/request-password-reset")
def request_password_reset(details: EmailRequest):
    require_mail_configuration()
    email = str(details.email).lower()

    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email))
        if user:
            token = create_password_reset_token(session, user.id)
            # Return value deliberately unused: this response must stay identical
            # whether or not the account exists (see the note above the return).
            send_password_reset_email(user.email, token)

    # Do not reveal whether an email address has an account.
    return {"message": "If an account exists, a password-reset email was requested. "
        "If it does not arrive, please contact COCEGN or try again later."}


@app.post("/auth/reset-password")
def reset_password(details: PasswordResetRequest):
    with SessionLocal() as session:
        reset = session.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == hash_token(details.token)
            )
        )
        if not reset or reset.used_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This password-reset link is invalid or has already been used.",
            )

        expires_at = reset.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now_utc():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This password-reset link has expired.",
            )

        user = session.get(User, reset.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This password-reset link is invalid.",
            )

        user.password_hash = password_hash.hash(details.password)
        reset.used_at = now_utc()
        # Password changes invalidate every existing sign-in session.
        session.execute(
            delete(UserSession).where(UserSession.user_id == user.id)
        )
        session.commit()

    return {"message": "Your password has been reset. You can now sign in."}


@app.post("/auth/verify-email")
def verify_email(details: VerifyEmailRequest):
    with SessionLocal() as session:
        verification = session.scalar(
            select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash
                == hash_token(details.token)
            )
        )

        if not verification or verification.used_at:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This verification link is invalid or has already been used.",
            )

        expires_at = verification.expires_at

        # SQLite returns a timezone-naive value during local development.
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at <= now_utc():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This verification link has expired.",
            )

        user = session.get(User, verification.user_id)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This verification link is invalid.",
            )

        user.email_verified = True
        # The server-approved initial administrator can finish setup without
        # waiting for another worker restart. Identity must be verified first.
        if user.email == os.getenv("ADMIN_EMAIL", "").strip().lower():
            user.is_admin = True
        verification.used_at = now_utc()

        session.commit()

        return {"message": "Email verified successfully."}


@app.post("/auth/login", response_model=CurrentUserResponse)
def login(details: LoginRequest):
    email = str(details.email).lower()

    with SessionLocal() as session:
        user = session.scalar(
            select(User).where(User.email == email)
        )

        # Verify a hash even for an unknown email to reduce account guessing.
        password_to_check = (
            user.password_hash if user else DUMMY_PASSWORD_HASH
        )

        password_is_correct = password_hash.verify(
            details.password,
            password_to_check,
        )

        if not user or not password_is_correct:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password.",
            )

        if not user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Verify your email before signing in.",
            )

        raw_session_token = create_session_token(session, user.id)

        response = JSONResponse(
            content={
                "id": user.id,
                "first_name": user.first_name,
                "email": user.email,
                "email_verified": user.email_verified,
                "is_admin": user.is_admin,
            }
        )

        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=raw_session_token,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax",
            max_age=int(SESSION_DURATION.total_seconds()),
            path="/",
        )

        return response


@app.get("/auth/me", response_model=CurrentUserResponse)
def get_current_user(
    ce_session: str | None = Cookie(default=None),
):
    if not ce_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You are not signed in.",
        )

    with SessionLocal() as session:
        user = find_session_user(session, ce_session)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your session is missing or has expired.",
            )

        return user


@app.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    ce_session: str | None = Cookie(default=None),
):
    if ce_session:
        with SessionLocal() as session:
            user_session = session.scalar(
                select(UserSession).where(
                    UserSession.token_hash == hash_token(ce_session)
                )
            )

            if user_session and not user_session.revoked_at:
                user_session.revoked_at = now_utc()
                session.commit()

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


@app.post("/auth/profile", response_model=CurrentUserResponse)
def update_profile(
    details: ProfileUpdateRequest,
    ce_session: str | None = Cookie(default=None),
):
    if not ce_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You must sign in to update your profile.",
        )

    with SessionLocal() as session:
        user = find_session_user(session, ce_session)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your session is missing or has expired.",
            )
        user.first_name = details.first_name.strip()
        user.last_name = details.last_name.strip()
        session.commit()
        session.refresh(user)
        return user


@app.get("/member/dashboard", response_model=MemberDashboardResponse)
def get_member_dashboard(
    ce_session: str | None = Cookie(default=None),
):
    if not ce_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="You must sign in to view the member dashboard.",
        )

    with SessionLocal() as session:
        user = find_session_user(session, ce_session)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your session is missing or has expired.",
            )

        return {
            "id": user.id,
            "first_name": user.first_name,
            "email": user.email,
            "email_verified": user.email_verified,
            "is_admin": user.is_admin,
            "greeting": f"Welcome back, {user.first_name}.",
            "membership_status": "Account verified",
        }
