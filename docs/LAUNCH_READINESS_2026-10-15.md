# COCEGN launch readiness — 15 October 2026

**Latest external state:** https://cocegn.vercel.app is live with hosted Neon
PostgreSQL migrated, seven form fixtures persisted, private-path denial verified,
and both application and Vercel rate limiting observed. A private database backup
was restored successfully. Latest backend suite: **83 passed**, including real
PostgreSQL. User reports updating Brevo API authorization, but the latest check is blocked
by provider Cloudflare error 1010 (browser signature banned). Provider resolution,
actual mail delivery and the administrator's verified account remain outstanding. HTTPS email support is tested and deployed; private mail settings await
provider authorization. DBeaver is installed and its private profile prepared; GUI
connection is unverified. See `docs/VERCEL_LAUNCH.md` for the current checkpoint;
entries below are historical evidence, not the current completion state.

**Historical assessment followed by implementation:** the original assessment
below predates the resumed work. See the dated progress record at the end and
`docs/VERCEL_LAUNCH.md` for the current deployment instructions. An unchecked item
below may now have local implementation evidence; external launch checks remain
outstanding unless explicitly recorded.

This is the working launch checklist requested after inspecting the current repository. Future launch work should use this file, verify each item against the code, and record completion evidence here. Older audits are background, not a current task list. This assessment does not authorise deployment or invent organisational decisions.

Only this report was created. Existing code, content, configuration, dependencies and project instructions were not changed. No real messages, payments or submissions were sent.

## What is being built now

Core Christian Educators Global Network (COCEGN) has a static public website and a separate, single-file FastAPI backend. There is no frontend build step. Production JavaScript expects API routes on the same origin as the website.

The current site has 30 HTML pages including the homepage and 404 page. Its two main purposes are educator growth/community and welfare/support for teachers and their families. It includes the Academy, child sponsorship, widow support, teacher support, Ministry to the Aged, State Coordinator applications, volunteering, partnerships and stories.

Bronze, Silver, Gold and Diamond applications save additional profile fields, values agreement, application consent and separate optional updates consent. Coordinator, volunteer, partnership and story submissions enter the private admin contact inbox. These are enquiries, not automatic programme enrolment or sponsorship assignments.

Accounts have email verification, Argon2 password hashes, hashed expiring tokens, HttpOnly cookie sessions and server-side admin checks. The member dashboard reports account verification; it does not manage membership approval, paid entitlements or a private resource library. Account creation and membership application are separate.

Payments default to disabled. Public giving routes direct visitors to enquiries/WhatsApp. Membership checkout explicitly refuses unconfirmed fees. Six local illustrative image sets are visibly labelled as AI-generated; the founder uses initials rather than an invented photograph.

## Evidence and limits

| Check | Actual result |
| --- | --- |
| Read instructions and current implementation | Reviewed `Agent.md`, `CLAUDE.md`, README, content/photo documents, backend, frontend script, page content, existing tests and validation scripts. |
| Static checks | `python3 -B scripts/check_site.py` passed for 30 pages: local links/anchors, basic metadata, heading counts, labels, image references and targeted stale-copy checks. This is not complete HTML or accessibility certification. |
| Browser checks | `python3 -B scripts/check_browser.py` passed 550 assertions across 28 pages at 320, 768 and 1440px, including seven mocked form flows. Required permission to run its local server outside the sandbox. Authenticated dashboards are excluded and API responses are mocked. |
| Backend tests | `PYTHONDONTWRITEBYTECODE=1 python3 -B -m pytest back_end/tests -q -p no:cacheprovider` returned 24 failures, all at import because `pwdlib` is absent. Application behaviour was not exercised. |
| Runtime available here | Python 3.13.12; project requires Python 3.14 or newer. `uv` is not on PATH. No dependencies were installed during this assessment. |
| Production services | Domain/DNS, hosting, HTTPS, reverse proxy, live database, SMTP delivery, backups and real admin access remain unverified. No deployment configuration was found in the repository. Absence here does not establish absence in your hosting account. |
| Working tree before report | Clean. |

## Required before launching the current forms and accounts

Unchecked items are outstanding or unverified, not claims that an external service is absent.

### 1. Confirm production destination and launch scope

- [ ] Supply the actual domain, hosting provider and intended database service. Record what is already configured externally before doing duplicate work.
- [ ] Confirm whether today's launch includes accounts and all public forms. The existing implementation supports an enquiry/application launch with checkout unavailable; it does not yet support a complete paid membership portal.
- [ ] Identify the person handling applications, messages, privacy requests and safeguarding concerns. Confirm the published phone/WhatsApp is monitored. Existing content records prior confirmation of +234 803 287 2739 and CAC RC 1546376 / 2018; do not replace those with guesses.

Done when: the production origin, service responsibilities and enabled features are recorded.

### 2. Establish the correct backend runtime and finish database readiness

- [ ] Use Python 3.14+ and the backend's locked dependencies, then run all existing tests successfully. The root `pyproject.toml` is unused scaffolding.
- [ ] Resolve `lifespan()` running `PRAGMA table_info(users)` unconditionally. This is SQLite-only and prevents PostgreSQL startup, even though `psycopg[binary]` is now declared and locked.
- [ ] Configure Alembic and actual migrations for the chosen production database. Alembic is declared and locked, but no migration environment/revisions are present. Installing the package alone does not migrate data.
- [ ] Set an explicit production `DATABASE_URL`, using the correct driver URL for the chosen service. Verify fresh startup and upgrade against a copy of any existing database, preserving old applications and adding profile/consent tables.
- [ ] Verify persistent storage, restricted database access, automated backups and an actual restore. Do not run experiments against the only copy of member data.

Done when: the intended database starts successfully, tests pass in the supported runtime, existing data survives an upgrade, and a backup restores successfully.

### 3. Configure safe public hosting

- [ ] Serve the website and `/auth`, `/member`, `/admin`, `/payments` and other API routes behind the same HTTPS origin. Use production process management rather than a development reload server.
- [ ] Set `ENVIRONMENT=production` and the actual HTTPS `FRONTEND_BASE_URL`; verify secure cookie behaviour, production CORS and generated email links. Keep secrets in private production configuration.
- [ ] Deploy only public HTML, `assets/`, `robots.txt` and the eventual sitemap to the static document root. Keep backend source, `.git`, environment files, databases, tests, scripts and internal documents private. Serving the repository root with `http.server` is a local workflow, not a production deployment plan.
- [ ] Configure security headers for static pages as well as API responses. FastAPI middleware protects responses passing through FastAPI; a separate static server needs its own configuration. Prevent caching of authenticated API responses containing personal data.
- [ ] Verify HTTP-to-HTTPS redirects, the real 404 response/status, private-path denial, uptime checks, restart behaviour and rollback.

Done when: production URLs behave correctly and private files cannot be downloaded.

### 4. Verify mail delivery and account recovery

- [ ] Configure the actual SMTP login/key, verified sender/domain and admin recipient. Follow the mail provider's domain-authentication requirements and test real inbox delivery with organisation-controlled accounts.
- [ ] Exercise registration → verification → login, password reset, logout, and expiry/reuse rejection. Confirm resetting a password invalidates previous sessions.
- [ ] Provide a usable way to resend verification links. `/auth/request-email-verification` exists, but current markup/JavaScript does not expose it. A missed or expired verification email currently leaves the visitor contacting the organisation for help.
- [ ] Verify confirmation emails and admin notices for applications, contact, newsletter and the specialised enquiry forms. Do not copy private enquiry text into admin notification emails.
- [ ] Establish monitoring for failed mail and a manual recovery procedure. Forms are saved before mail is attempted, but there is no durable mail retry queue. `/health` reports only that mail settings are present, not successful delivery.

Done when: real verification/recovery emails work, users can recover an expired verification link, and staff can find saved submissions even when notifications fail.

### 5. Add abuse controls and verify access boundaries

- [ ] Protect login, registration, verification resend, password reset and public submissions with effective rate limits. No application rate limiting exists; inspect any provider/proxy controls before choosing implementation.
- [ ] Verify cookie-authenticated write protections, including the production origin/CSRF boundary, using the actual deployment. CORS and SameSite settings should not be treated as evidence that every request boundary has been tested.
- [ ] Stop production mail fallbacks/errors from exposing email addresses, verification/reset links or private content in logs. `send_email()` currently prints recipient/body when SMTP is missing and recipient/server error on failure. Production logging needs redaction and restricted access.
- [ ] Bootstrap the intended verified administrator using `ADMIN_EMAIL` and prove that admin APIs return no member data to signed-out or ordinary accounts. Verify the admin can read the new application fields and all enquiry types.
- [ ] Add meaningful security regression coverage for login verification, cookie flags, token expiry/single use, password-reset session invalidation and admin authorisation. Existing tests mainly exercise configuration and route helpers; one admin-data test deliberately mocks the access check.

Done when: abuse controls are demonstrated, sensitive logs are avoided, and authenticated/unauthenticated access behaviour is tested.

### 6. Complete organisational review and operational privacy handling

- [ ] Obtain approved privacy/terms wording. Current pages explicitly say retention/service-provider details and full membership/giving terms await review. Record actual retention, providers, responsible contact and the procedure for access/correction/deletion requests. This report does not determine legal compliance.
- [ ] Establish a working unsubscribe process before sending newsletters. The current backend saves subscriptions but has no unsubscribe endpoint or subscriber suppression workflow; the policy currently directs requests to the team.
- [ ] Confirm staff can honour privacy and safeguarding requests, including removing records from mailing tools and handling backups appropriately under the approved policy. A self-service deletion UI is not required merely to implement a manual process.
- [ ] Review the existing programme and giving claims with the organisation: available professional help, cooperative/loan schemes, counselling, allocation of gifts and promised beneficiary updates must match actual operations. Do not invent replacements or remove supplied wording without review.

Done when: approved wording and real staff procedures agree with how the deployed system handles information and enquiries.

### 7. Run production acceptance checks before announcing launch

- [ ] Run the static/browser checks again after any changes, plus backend tests in the supported environment.
- [ ] With controlled test identities, submit each real form through the HTTPS site and confirm persistence and admin visibility. Mocked browser tests do not establish this.
- [ ] Verify member/admin login, access denial, logout, reset and verification through the production proxy. Check dashboard layouts on phones, since the existing browser suite excludes them.
- [ ] Confirm `PAYMENTS_ENABLED=false`, membership checkout remains unavailable, and public giving copy matches the enabled features.
- [ ] Review the deployed pages on a real phone and keyboard, including menu, form feedback, images and contact links. Record results and remove only controlled test records through an agreed process.

Done when: all enabled visitor journeys work against production, staff can act on submissions, and remaining limitations are explicitly accepted.

## Required only before enabling checkout

These do not need to block an enquiry-only launch while checkout remains unavailable.

- [ ] Receive approved tier fees, eligibility/benefits, giving arrangements and payment/refund wording from the organisation. Current code correctly refuses all membership charges.
- [ ] Confirm the organisation's approved Paystack account and private production credentials.
- [ ] Implement authenticated Paystack webhook processing with signature validation, reference/amount/currency checks and idempotency. No webhook currently exists; browser return alone is insufficient.
- [ ] Fix payment verification's mismatch fallback: when Paystack reports `success` but an amount/currency/reference check fails, the function currently returns the provider's `success` status anyway. The database is not marked paid, but the frontend displays “Payment confirmed.” Reject mismatches and test that the UI cannot claim success.
- [ ] Add bounded donation amounts and test checkout failures, retries, duplicate callbacks, delayed webhooks and reconciliation. Enable payments only after an observed end-to-end test and approved launch decision.

## Finishing work that need not block the current enquiry launch

- [ ] After the real domain is confirmed, generate `sitemap.xml` with the existing script and add its absolute URL to `robots.txt`. Add canonical/social sharing metadata with approved URLs/assets. `robots.txt` already exists.
- [ ] Replace illustrations with consented real photos, founder portrait and registration documentation when supplied. Keep current illustration labels until replacement; use `docs/PHOTO_REPLACEMENT.md`.
- [ ] Publish actual event dates, podcast links, approved testimonials/impact figures and beneficiary profiles only when available and authorised. Current pending states do not need fictional content to launch.
- [ ] Add CI, fuller accessibility checks, admin audit records and pagination/search as follow-up work. Admin lists currently return only the newest 100 rows, so a retrieval procedure is needed if volume reaches that limit.
- [ ] Consider durable email retries and a fuller membership/resource workflow separately, based on agreed requirements. Do not expand today's launch into an unrequested CMS or redesign.
- [ ] Reconcile stale project documentation after implementation. `Agent.md`/`CLAUDE.md` incorrectly describe absent tests, older pages/pricing/legal copy, missing robots and disabled API documentation. `FastAPI(...)` currently leaves its default docs/OpenAPI enabled. README and `.env.example` incorrectly say the PostgreSQL driver is missing; the remaining startup/migration issue is real.
- [ ] Review removal of the tracked `back_end/__pycache__/back_end.cpython-314.pyc` separately. Do not run destructive Git cleanup as part of this report.

## Order for the next work session

1. Record the real hosting/domain/database status and enabled launch scope.
2. Fix runtime/database readiness and pass the backend checks.
3. Complete hosting, SMTP, admin access and abuse/logging controls.
4. Obtain outstanding organisational decisions and put privacy/submission handling into operation.
5. Exercise real production journeys and record the launch decision.

For each completed item, record: what changed, files/settings affected (without secrets), observed verification result, date and anything still unverified. Preserve the existing account protections and completed content work. Do not mark an item complete from code inspection alone when it requires a live service test.

## Resumed implementation — 15 October 2026

User confirmed Vercel hosting with an initial `vercel.app` address, PostgreSQL,
and DBeaver management. Local memory/storage must be considered. Resource check:
3.7 GiB total RAM, 1.7 GiB available at inspection, 192 GB free disk. No Docker
stack was installed. An isolated PostgreSQL 18 server was used for tests only.

Observed local evidence:

- Installed Python 3.14.8 and the backend's locked dependencies. Backend tests
  pass: **45 passed**, including actual PostgreSQL account journeys, SQLite
  compatibility, migrations, payment mismatch handling, request controls and
  public-bundle privacy. Mail and payment-provider calls are mocked.
- PostgreSQL migration output matches the ORM schema with no Alembic metadata
  differences. The actual root Vercel entrypoint starts on that migrated test
  database, returns `/health`, rejects private source/configuration URLs with
  404, and reports payments disabled.
- Alembic baseline adopts compatible legacy tables and creates the missing tables;
  API startup checks revisions instead of running SQLite-only schema alterations.
- Rate limiting and cookie-request origin checks are implemented. Rate limiting
  is per process: Vercel Firewall controls still require configuration and live
  verification. Private API responses receive `Cache-Control: no-store`.
- Mail failure logging no longer prints recipient, subject, body, token or raw
  provider error. Live SMTP credentials and inbox delivery remain unverified.
- Successful provider responses with mismatched payment details are rejected;
  matching payment handling passes regression checks. No webhook was added and
  checkout remains disabled.
- A verification-resend form is available on the login page. Browser checks pass
  **563 assertions across 28 pages**, including mocked resend states. Static
  checks pass for all **30 HTML pages**.
- Vercel configuration, root API entrypoint, matching root dependencies/lockfile,
  static security headers and a public-only build script are implemented. A
  regression test demonstrates exclusion of private files and symlink rejection.
- DBeaver Community 26.2.2 installed under `~/.local/opt/` with a launcher and
  application-menu entry. Installation occupies about 205 MB; Java heap configured
  to 64 MB initial / 512 MB maximum. Bundled Java runs successfully. Actual GUI
  connection to the eventual hosted database remains unverified.

Not yet launched: Vercel authentication/connection is unconfirmed; no hosted
database URL, SMTP settings or approved admin email were found in the current
environment or project configuration. Provider provisioning, production migration,
real SMTP delivery, admin bootstrap, deployment-wide abuse controls, backups/restore,
privacy approval and live acceptance checks remain outstanding. No production
deployment or real messages/payments have been performed in this resumed work.
