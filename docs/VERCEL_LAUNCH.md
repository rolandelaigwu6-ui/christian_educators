# Vercel launch — PostgreSQL and DBeaver

Target confirmed on 15 October 2026: Vercel, initially using a `vercel.app`
address. PostgreSQL stores production data; DBeaver Community is the desktop
management client. No domain purchase or paid subscription is authorised here.

## Current deployment checkpoint — 15 October 2026

- Production address: **https://cocegn.vercel.app**, project `learn2earn2/cocegn`.
  Last verified production deployment: `dpl_2QXv3iVgh1FGvJYCiGcZQNtE2ZQy`.
- Latest deployment passed 45 read-only live checks: all 30 HTML pages return
  200, protected APIs reject anonymous access, private source/configuration paths
  return 404, updated JavaScript/retry panels are present, and payments stay disabled.
  Static security headers and private API `no-store` responses were verified.
- Neon PostgreSQL `cocegn-postgres` is provisioned on `free_v3` in `fra1`, attached
  only to production. Pooled application and direct migration connections work.
  Alembic revision `20261015_01` is applied; schema comparison found no differences.
- A private PostgreSQL dump was restored into a disposable local database:
  11 tables and the migration revision verified. This proves a manual snapshot
  and restore, not a scheduled backup policy. Backup location/manifest is private
  under `.vercel/backups/`; do not commit or publish it.
- Production environment and HTTPS origin are configured. Payments remain disabled.
  Administrator and notification email: `rolandelaigwu6@gmail.com`.
  The account still needs registration and real email verification.
- Seven controlled membership/contact/newsletter fixtures were saved successfully
  and checked directly in PostgreSQL. No mail was sent. Admin visibility and
  cleanup of these exact fixtures remain pending administrator access.
- Vercel Firewall rule `COCEGN form protection` limits protected POST routes to
  30 requests per minute per IP. A live 31-request invalid-login check returned
  19 validation responses and 12 rate-limit responses, including an observed
  platform block. No accounts or messages were created by this check.
- Backend suite: **83 passed**, including actual disposable PostgreSQL journeys
  and the new Brevo HTTPS transport. Browser suite: **627 assertions** across
  28 pages; static checks: 30 pages. Automated mail is mocked.
- User reports saving Automatic authorization for API IPs. Subsequent local
  sender checks return HTTP 403 / Cloudflare 1010 (`browser_signature_banned`),
  a provider edge-security block before API credential validation. The response
  instructs against retries and requires site-owner resolution. No further
  requests should be made until Brevo resolves it. The active sender and key
  remain unverified; SMTP restrictions were not changed by this agent.
- HTTPS mail transport is implemented, tested and deployed.
  No mail credentials have been uploaded to Vercel. Do not treat presence of
  settings or provider acceptance as proof of inbox delivery.
- DBeaver is installed with a 512 MB Java heap cap. A private, read-only production
  connection profile and COCEGN database launcher are prepared; GUI/JDBC
  connection remains unverified. The local PostgreSQL test server is stopped.

Deployed payment-readiness work adds signed, bounded Paystack notifications with exact
transaction checks and idempotent settlement, a private administrator payment
list, whole-naira/storage-capacity input checks and production test-key rejection.
All 75 backend tests pass; no real payment or Paystack sandbox checkout has been
performed. The owner confirms the Paystack account exists but is not activated.
See `docs/PAYMENTS_LAUNCH.md` for activation steps and outstanding requirements.

Account interface checks now cover duplicate-submit protection for login,
registration, reset requests, password changes and administrator grants. Pending
requests disable their button and expose `aria-busy`; failures allow retries.
Member/admin service errors show a retry panel instead of pretending the visitor
signed out. Logout navigates away only after the API confirms success; failures
warn that the session may remain active. The browser suite verifies these paths
with mocked responses and keeps private dashboard content hidden on load errors.
These interface checks do not replace live email/admin acceptance.

Password-reset and verification-resend endpoints now return the same explicit
503 outage response for every address when mail settings are absent. They do not
look up accounts or create replacement tokens during that outage. With mail
settings present, generic responses describe a request rather than claiming
inbox delivery. Eight additional SQLite/PostgreSQL checks cover outage handling,
unchanged token counts and identical known/unknown-account responses; the full
backend suite passes 83 tests. This corrects misleading feedback; Brevo delivery
and live password-reset receipt remain unresolved.

Frontend visual upgrade reuses the local educator illustration as the homepage
background, preserving its label and the blue/gold/cream palette. CSS stages the
hero entrance; native IntersectionObserver reveals content once, while hover and
focus states add depth to cards and buttons. Reduced-motion settings disable
movement, keyboard focus reveals targets, and content stays visible without
observer support. No dependencies or remote assets were added. Static checks
pass all 30 pages, the existing browser suite passes 627 assertions, and
`scripts/check_motion.py` passes 31 normal/reduced/fallback checks. Desktop and
phone previews were captured and visually reviewed.

Organisation design refinement: a shared contact strip and navigation on all
30 pages; compact breadcrumbs retaining Back; a clearer organisational homepage
with purpose, two programme pillars, Academy, support and participation sections;
consistent typography, button/card geometry and a more restrained motion system.
The existing image background, blue/gold/cream palette and illustration labels
remain. Core section titles now describe their destination directly. No new
organisation credentials, dates, impact figures or payment capability were added.
Static checks pass 30 pages, browser checks pass 627 assertions and motion
checks pass 31 cases; 45 live checks pass. The published homepage, About page,
stylesheet and script match the reviewed files. Phone, desktop,
full-homepage and About previews were visually reviewed.

**Launch acceptance remains incomplete:** finish Brevo authorization, upload
mail settings and redeploy, verify actual email delivery and the intended admin
account, inspect saved submissions through admin APIs, then remove only the
controlled fixture records. Organisation-approved policy wording and manual
privacy/unsubscribe handling remain owner decisions.

## Deployment layout

- Deploy from the repository root using Vercel's FastAPI preset and Python 3.14.
- Root metadata and lockfile match the tested backend dependencies. `app.py`
  exports the existing backend without changing API paths.
- `python scripts/prepare_public.py` generates `public/` from the HTML, assets
  and robots allowlist. Vercel serves these through its CDN. Backend source,
  configuration, database files, internal documents and tests are never copied.
- The builder rejects symlinks and refuses to replace an unrecognised output
  directory. `public/` is generated and Git-ignored.
- `vercel.json` applies security headers to static responses as well as the API.
- `.vercelignore` excludes local configuration, local virtual environments,
  personal tool folders, tests and database files from CLI uploads.

## Hosted database and private settings

Vercel needs a hosted PostgreSQL service reachable over TLS. The database on a
laptop is for development/testing, not production hosting. A provider such as
Neon can be attached through Vercel's Marketplace; confirm its plan/limits before
provisioning. Prefer a pooled production URL where the provider offers one, and
a direct URL for schema migrations.

Set these in the appropriate Vercel environment, never in committed files:

| Setting | Required value |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `FRONTEND_BASE_URL` | Exact assigned HTTPS production origin, without a trailing slash |
| `DATABASE_URL` | Hosted PostgreSQL connection URL with provider-required TLS settings |
| `BREVO_API_KEY` | Brevo HTTPS API key; preferred on this Vercel deployment |
| `SMTP_HOST`, `SMTP_PORT` | Optional fallback SMTP endpoint and port when no API key is configured |
| `SMTP_USERNAME`, `SMTP_PASSWORD` | SMTP login and SMTP key, not the account password |
| `SMTP_FROM_EMAIL` | Verified sender address |
| `SMTP_USE_TLS` | `true` for the existing STARTTLS configuration |
| `ADMIN_EMAIL` | Organisation-approved administrator's account email |
| `ADMIN_NOTIFICATION_EMAIL` | Monitored notification recipient |
| `PAYMENTS_ENABLED` | `false` |

Standard `postgres://` and `postgresql://` URLs automatically select Psycopg;
explicit `postgresql+psycopg://` also works. Preserve URL-encoded credentials.
Preview deployments must use a separate test database and appropriate origin;
do not attach preview builds to production member records.

## Apply migrations once before API startup

Use a privately configured environment pointing at the intended database. Back
up existing data first. From the repository root with backend dependencies:

```bash
uv run --project back_end alembic -c back_end/alembic.ini upgrade head
```

API startup checks the migration revision and refuses an unmigrated database.
Migrations are deliberately not run on each function invocation or automatically
on every preview build. The baseline does not support destructive downgrades;
rollback means restoring a reviewed backup or rolling forward with a fix.

## DBeaver on this computer

DBeaver Community 26.2.2 is installed at
`~/.local/opt/dbeaver-26.2.2/dbeaver/`, with a `~/.local/bin/dbeaver` launcher and
an application-menu entry. The Java heap starts at 64 MB and is capped at 512 MB;
total process memory includes additional native/JVM overhead. Installation uses
about 205 MB on disk and has no autostart or background service.

The application-menu entry **COCEGN database** opens the prepared private
production workspace, with read-only mode selected by default. Its profile uses
the direct hosted connection. GUI/JDBC connection has not yet been verified.
For a new connection, use the hosted hostname, database, username and password. Enable the provider's required SSL settings. DBeaver may
download its PostgreSQL JDBC driver on first use. Keep connection credentials
private. Database administration must not require exposing a laptop database to
the public internet.

## Acceptance before announcing launch

1. Confirm the deployed homepage, all public forms, real 404 status and denied
   access to private paths such as `/back_end/.env` and `/.git/config`.
2. Register an organisation-controlled test account; verify delivery to the real
   inbox; verify email; log in; resend verification; reset password; log out.
3. Confirm old sessions fail after reset and ordinary members cannot access admin
   APIs. The configured `ADMIN_EMAIL` receives admin status when its real email
   verification succeeds; verify that account before using admin login.
4. Submit controlled membership/contact/newsletter and specialised enquiries;
   confirm persistence and visibility to the intended administrator. Emails alone
   do not prove that submissions were saved or received by staff.
5. Configure and verify Vercel Firewall rate controls for auth and public forms.
   The application limiter is bounded but per process; it does not enforce a
   deployment-wide limit across serverless instances. Proxy/IP behaviour must be
   checked on Vercel. Do not claim global abuse protection from local tests.
6. Verify database backups and a restore, responsible staff, approved privacy and
   programme wording, and a manual unsubscribe process before sending newsletters.
7. Check phone/keyboard layouts and ensure checkout stays disabled.

## Local verification

```bash
python3 -B scripts/check_site.py
python3 -B scripts/check_browser.py
uv run --project back_end pytest back_end/tests -q
```

Optional real PostgreSQL account tests use `TEST_POSTGRES_URL` pointing at a
disposable test database. Each test creates and removes its own generated schema.
Never use production credentials for these tests. Mail is mocked in automated
checks; SMTP delivery and live Vercel routing require separate acceptance checks.

Sources: [Vercel FastAPI deployment](https://vercel.com/docs/frameworks/backend/fastapi),
[Python runtime](https://vercel.com/docs/functions/runtimes/python),
[PostgreSQL integrations](https://vercel.com/docs/postgres),
[DBeaver Community download](https://dbeaver.io/download/).
