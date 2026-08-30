from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import json
import os
import secrets
import smtplib
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import Cookie, FastAPI, HTTPException, Request as FastAPIRequest, Response, status
from fastapi.middleware.cors import CORSMiddleware
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
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


DATABASE_URL = "sqlite:///./christian_educators.db"
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://127.0.0.1:5500")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL")
SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
ADMIN_NOTIFICATION_EMAIL = os.getenv("ADMIN_NOTIFICATION_EMAIL")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY")
PAYMENTS_ENABLED = os.getenv("PAYMENTS_ENABLED", "false").lower() == "true"


engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

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
    donation_amount: int | None = Field(default=None, ge=100)


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


def print_development_verification_link(email: str, token: str):
    verification_url = f"{FRONTEND_BASE_URL}/pages/verify-email.html?token={token}"
    send_email(
        email,
        "Verify your Christian Educators account",
        (
            "Welcome to Christian Educators Global Network.\n\n"
            "Verify your email address by opening this link within one hour:\n"
            f"{verification_url}\n\n"
            "If you did not create this account, you can ignore this email."
        ),
    )


def send_password_reset_email(email: str, token: str):
    reset_url = f"{FRONTEND_BASE_URL}/pages/reset-password.html?token={token}"
    send_email(
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
    """Send SMTP email, or print it locally when SMTP has not been configured."""
    if not recipient:
        return False

    if not SMTP_HOST or not SMTP_FROM_EMAIL:
        print("\n--- DEVELOPMENT EMAIL ---")
        print(f"To: {recipient}")
        print(f"Subject: {subject}")
        print(body)
        print("-------------------------\n")
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
        print(f"Email delivery failed for {recipient}: {error}")
        return False


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
    Base.metadata.create_all(engine)

    # SQLite does not add new columns during create_all(), so keep existing
    # local databases compatible as the application evolves.
    with SessionLocal() as session:
        columns = {
            row[1]
            for row in session.connection().exec_driver_sql(
                "PRAGMA table_info(users)"
            )
        }
        if "is_admin" not in columns:
            session.connection().exec_driver_sql(
                "ALTER TABLE users ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0"
            )
            session.commit()

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


@app.middleware("http")
async def add_security_headers(request: FastAPIRequest, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.get("/health")
def health_check():
    return {
        "status": "ok",
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

    membership_prices = {
        "basic": 65700,
        "coverage": 266700,
        "student": 25500,
        "retired": 52300,
    }
    email = str(details.email).lower()

    if details.payment_type == "membership":
        if details.tier not in membership_prices:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Select a paid membership tier.",
            )
        amount_ngn = membership_prices[details.tier]
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


@app.get("/payments/verify/{reference}")
def verify_payment(reference: str):
    with SessionLocal() as session:
        payment = session.scalar(select(Payment).where(Payment.reference == reference))
        if not payment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found.")

    transaction = paystack_request(f"/transaction/verify/{reference}")
    if (
        transaction.get("status") == "success"
        and transaction.get("reference") == reference
        and transaction.get("amount") == payment.amount_kobo
        and transaction.get("currency") == "NGN"
    ):
        with SessionLocal() as session:
            payment = session.scalar(select(Payment).where(Payment.reference == reference))
            payment.status = "success"
            payment.paid_at = now_utc()
            session.commit()
        return {"status": "success", "amount_ngn": payment.amount_kobo // 100}

    return {"status": transaction.get("status", "pending")}


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
        return [
            {
                "id": item.id,
                "name": f"{item.first_name} {item.last_name}",
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
    allowed_tiers = {"basic", "coverage", "student", "retired", "gift", "unsure"}
    email = str(details.email).lower()

    if details.tier not in allowed_tiers:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Select a valid membership option.",
        )

    if not details.marketing_consent:
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
            marketing_consent=True,
            created_at=now_utc(),
        )
        session.add(application)
        session.commit()

    send_email(
        email,
        "We received your membership application",
        (
            "Thank you for applying to Christian Educators Global Network. "
            "Our member-care team will review your application and contact you about next steps."
        ),
    )
    send_email(
        ADMIN_NOTIFICATION_EMAIL,
        "New membership application",
        "A new membership application was submitted. Review it in the admin dashboard.",
    )
    return {"message": "Your membership application has been received."}


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

    send_email(
        email,
        "We received your message",
        "Thank you for contacting Christian Educators Global Network. Our member-care team will respond within two business days.",
    )
    send_email(
        ADMIN_NOTIFICATION_EMAIL,
        "New contact message",
        "A new contact message was submitted. Review it in the admin dashboard.",
    )
    return {"message": "Your message has been received."}


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
            return {"message": "This email is already subscribed."}

        subscriber = NewsletterSubscriber(
            email=email,
            first_name=details.first_name.strip() if details.first_name else None,
            subscribed_at=now_utc(),
        )
        session.add(subscriber)
        session.commit()

    send_email(
        email,
        "Welcome to the Christian Educators newsletter",
        "You are now subscribed to receive encouragement and updates from Christian Educators Global Network.",
    )
    send_email(
        ADMIN_NOTIFICATION_EMAIL,
        "New newsletter subscriber",
        "A new newsletter subscription was received. Review it in the admin dashboard.",
    )
    return {"message": "You are subscribed to the newsletter."}


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
        print_development_verification_link(user.email, token)

        return user


@app.post("/auth/request-email-verification")
def request_email_verification(details: EmailRequest):
    email = str(details.email).lower()

    with SessionLocal() as session:
        user = session.scalar(
            select(User).where(User.email == email)
        )

        if user and not user.email_verified:
            token = create_verification_token(session, user.id)
            print_development_verification_link(user.email, token)

    # Same response whether the email exists or not.
    return {
        "message": (
            "If an account needs verification, "
            "a verification email has been sent."
        )
    }


@app.post("/auth/request-password-reset")
def request_password_reset(details: EmailRequest):
    email = str(details.email).lower()

    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.email == email))
        if user:
            token = create_password_reset_token(session, user.id)
            send_password_reset_email(user.email, token)

    # Do not reveal whether an email address has an account.
    return {"message": "If an account exists, a password-reset email has been sent."}


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
