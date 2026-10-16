# Core Christian Educators Global Network

Vercel deployment: see [the launch guide](docs/VERCEL_LAUNCH.md). The root
`pyproject.toml` and `uv.lock` now provide the same dependencies as the backend
for Vercel; `app.py` exports the existing API. No frontend framework is required.

## Local development

Start the frontend from the project root:

```powershell
uv run python -m http.server 5500 --bind 127.0.0.1
```

In another terminal, start the API:

```powershell
cd back_end
uv sync --locked
uv run alembic -c alembic.ini upgrade head
uv run uvicorn back_end:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:5500`.

## Configuration

Backend settings come from two places, in this order:

1. **Real environment varia.bles** — anything exported in the shell wins.
2. **`back_end/.env`** — created by copying `back_end/.env.example`. It is read
   automatically at startup and is gitignored.

```bash
cp back_end/.env.example back_end/.env
```

Never commit real API keys, SMTP keys, passwords, or the SQLite database.

### Email

Email uses Brevo. For HTTPS delivery, set a private `BREVO_API_KEY` and the verified
`SMTP_FROM_EMAIL`; the API key is different from an SMTP key. When an API key is
configured it takes precedence over SMTP, without changing provider IP protections.
Otherwise email uses the SMTP relay described below. **Without a sender and either
an API key or SMTP host, no email is sent**. Only failure categories are logged; recipients,
message bodies and tokens are not printed. `GET /health` reports `"mail_configured": false` in that state, so check it first
if mail is not arriving.

When mail settings are absent, password-reset and verification-resend requests
return the same 503 outage message for every email address and create no new
tokens. With settings present, their generic response confirms only the request,
not inbox delivery; it never exposes whether an account exists or a particular
send failed. Actual provider access and inbox delivery require separate checks.

Setting those two variables is not enough on its own. `SMTP_PASSWORD` must be the **SMTP
key**, `SMTP_USERNAME` is the **SMTP login** (which may be a generated
`...@smtp-brevo.com` address rather than your signup email), and `SMTP_FROM_EMAIL` must be
a **verified sender** or sit on a domain authenticated with SPF/DKIM/DMARC. Brevo rejects
unverified senders even with correct credentials. See the comments in
`back_end/.env.example` for the details.

### Database

`DATABASE_URL` defaults to `sqlite:///./christian_educators.db` — a SQLite file resolved
relative to the **working directory**, so starting the backend from a different directory
opens a different database. That is fine for local development; set `DATABASE_URL`
explicitly for anything real.

**PostgreSQL is the production database. DBeaver is the desktop client used to
manage it.** Psycopg and Alembic are included in the locked backend dependencies.
Set `DATABASE_URL` in private configuration:

```text
postgresql+psycopg://USER:URL_ENCODED_PASSWORD@HOST:5432/DATABASE
```

Use your provider's TLS settings, typically `?sslmode=require` for a managed
service. In DBeaver select PostgreSQL and use the same host, port, database and
credentials with the provider's SSL settings. Never publish credentials.

Back up any existing database, then run `uv run alembic -c alembic.ini upgrade
head` from `back_end/` before starting the API. The baseline creates a fresh schema
or adopts compatible existing tables without dropping rows. Unknown missing
columns fail explicitly for review. Startup checks the migration revision and
refuses an unmigrated database; it never changes the schema automatically.
Rollback requires a reviewed backup; the baseline cannot be automatically dropped.

### Payments

`PAYMENTS_ENABLED` is deliberately `false`. Do not enable it until the organisation's Paystack account is approved, the public domain is live over HTTPS, and Paystack webhooks have been verified.

The signed notification endpoint is `POST /payments/webhook`; configure its exact
HTTPS URL in Paystack for the matching environment. It validates raw-body
HMAC-SHA512 and known transaction details, and duplicate notifications preserve
the original settlement time. It remains available for existing payments when
new checkout is disabled. Administrators can review the latest 100 records at
`GET /admin/payments` and on their dashboard; reconcile bank payouts in Paystack.
Production checkout refuses missing/test keys. Donation amounts must be whole
naira within the existing database integer capacity; membership fees remain
unavailable. See [payment readiness and activation](docs/PAYMENTS_LAUNCH.md).

## Launch checklist

- Supply verified organisation name, contact details, domain, legal status, privacy terms, and membership-benefit wording.
- Replace all sample testimonials, articles, events, impact statements, and placeholder contact information.
- Verify the production sending domain in Brevo using SPF/DKIM records.
- Deploy the frontend and API using HTTPS, PostgreSQL, backups, and private configuration. Run migrations before starting the API — see Configuration → Database.
- In production, put the API behind the same HTTPS domain (or a trusted reverse proxy) so the frontend can use same-origin `/auth` and `/admin` requests.
- Restrict CORS to the production frontend URL and remove local-development origins.
- Configure the organisation's Paystack Live account, webhook URL, and Live Secret Key only on the production host.
- Review legal claims, data-retention practice, tax language, and consent wording with the organisation's authorised representative.

## September 2026 website upgrade

The public site follows the supplied COCEGN Website Copy and Website Blueprint.
See [content status](docs/CONTENT_STATUS.md) for implemented pages, confirmed details,
and content or services still needed for launch. The existing README configuration
and deployment requirements above still apply.

Six realistic, clearly labelled illustrative image sets are included.
[Replace them with real photos](docs/PHOTO_REPLACEMENT.md) using the shared filenames
or the included `scripts/replace_photo.py` command; captions and alt text can be
updated across all affected pages at once.

Membership now offers Bronze, Silver, Gold and Diamond. Run migrations to create the
new application-profile and consent tables; existing records are preserved.
Membership checkout stays unavailable until actual fees are supplied. Coordinator,
volunteer, partner and story submissions appear in the admin **Enquiries & applications** table.

Validation commands (no frontend package installation required):

```bash
python3 scripts/check_site.py
python3 scripts/check_browser.py  # requires an installed Chrome/Chromium browser
python3 scripts/check_motion.py   # normal/reduced motion and visible-content fallbacks
cd back_end
uv run pytest tests -q
```

The browser checks use mocked submissions and do not send real messages.

The homepage uses the existing local educator illustration as a full-width
background with a blue readability overlay and its illustration label intact.
Native CSS entrances and observer-driven content reveals retain the existing
palette. Reduced-motion preferences disable movement; content remains visible
without observer support, and keyboard focus reveals its target immediately.
No animation library, remote image, font or frontend dependency is required.
The organisation layout adds consistent navigation/contact information across
all 30 pages, compact breadcrumbs with a Back action, and a homepage organised
around COCEGN’s purpose, programme pillars, Academy and participation routes.
Registration details and programme descriptions use the supplied organisation
information; illustrative photographs remain labelled.
After choosing the actual domain, run `scripts/generate_sitemap.py --base-url` with
its HTTPS origin, as described in the content-status document.
