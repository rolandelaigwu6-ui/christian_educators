# Christian Educators Global Network — Agent Instructions

> This file replaces an earlier `Agent.md` that described **SoTeach**, a Go-language AI
> tutoring system (`tutor/`, `session/`, `ai/prompts/`, `go test`). None of that exists in
> this repository. If you find references to Go, a tutoring engine, learners, or
> `go test ./tests/` anywhere, they are from that unrelated document and must be ignored.

---

## 1. What this project is

**Christian Educators Global Network (CEGNP)** — the public website and member portal for a
nonprofit professional association of Christian educators.

It is a **static frontend plus a small FastAPI backend**. It is not a SPA, not a mobile app,
and not a tutoring product. The dominant risk in this codebase is not algorithmic
complexity — it is **handling real people's account data and money**, and the organisation's
legal exposure over claims published on the site.

Two things follow from that, and they govern everything below:

1. **Security and privacy of member data outrank feature delivery.**
2. **Claims about the organisation are not ours to invent.** Pricing, legal status, coverage
   benefits, and response-time promises must be supplied by the organisation, not guessed.

---

## 2. Source-of-truth hierarchy

### Level 1 — the code itself

`back_end/back_end.py` is the single authoritative description of backend behaviour. It is one
file. **Read it before changing anything.** Where this document and the code disagree, the code
is right and this document is stale — fix this document.

### Level 2 — `README.md`

Authoritative for: how to run locally, environment configuration, and the pre-launch checklist.
Short and current.

### Level 3 — `readme` (no extension)

A **historical frontend audit** written before the backend existed. It is genuinely useful for
the *must-fix-before-launch* list in §9, but parts of it are **now factually wrong** and must
not be acted on:

> It states that `assets/js/main.js` "lets anyone log in with any email/password and saves
> identity information in localStorage."

That is **no longer true**. `main.js` was since rewritten to call the real API and store
nothing in browser storage (see the file's own header comment, and §8 invariant 1). The audit
predates the backend entirely. Treat its *findings* as leads, verify each one against the code,
and do not treat its *description of main.js* as current.

### There is no Level 4

There is no Blueprint directory, no design spec, and no product requirements document in this
repository. **When you need product behaviour that the code does not already encode, stop and
ask.** See §13.

---

## 3. Repository map

```text
christian_educators/
├── Agent.md              ← this file
├── CLAUDE.md             ← short form, auto-loaded by Claude Code
├── README.md             ← how to run; launch checklist
├── readme                ← historical audit (see §2)
├── index.html            ← homepage (root-relative asset paths)
├── 404.html              ← error page (root-relative asset paths)
├── pages/*.html          ← 20 pages (../-relative asset paths)
├── assets/
│   ├── css/style.css     ← the only stylesheet (~170 lines)
│   ├── js/main.js        ← the only JavaScript; all client behaviour
│   └── img/
├── back_end/
│   ├── back_end.py       ← THE ENTIRE BACKEND (single file, ~1200 lines)
│   ├── .env.example      ← committed template; .env is gitignored
│   ├── .env              ← your real config; gitignored, never commit it
│   ├── tests/            ← pytest suite (test_env_loading.py)
│   ├── pyproject.toml    ← backend dependencies
│   └── christian_educators.db   ← gitignored
├── pyproject.toml        ← ⚠ unused `uv init` scaffolding
└── src/christian_educators/__init__.py   ← ⚠ unused scaffolding
```

The root `pyproject.toml` and `src/` are leftover `uv init` output. **Nothing uses them.** The
real project metadata is `back_end/pyproject.toml`. Do not build on the root scaffolding, and
do not "consolidate" the two without being asked — that is a separate decision.

### Language and tooling

- Python **3.14** (pinned in `.python-version`), managed by **uv**
- Backend deps: `fastapi`, `sqlalchemy` 2.x, `pwdlib[argon2]`, `pydantic[email]`, `uvicorn`
- Frontend: **no build step, no framework, no bundler, no npm.** Plain HTML, CSS, and vanilla
  ES5-style JavaScript in an IIFE. Do not introduce a framework, a build tool, or a CDN dependency.

### Running it

The frontend and API are **two separate processes on two ports**:

```bash
# terminal 1 — frontend
uv run python -m http.server 5500 --bind 127.0.0.1

# terminal 2 — API
cd back_end
uv run uvicorn back_end:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:5500`. `main.js` detects localhost and points at `http://127.0.0.1:8000`;
in production it uses same-origin `""` and expects a reverse proxy in front of the API.

---

## 4. The API surface

One FastAPI app, no routers, no versioning prefix. All routes live in `back_end/back_end.py`.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/health` | public | status + payments/mail flags |
| POST | `/auth/register` | public | create account (Argon2 hash) |
| POST | `/auth/request-email-verification` | public | resend verification |
| POST | `/auth/verify-email` | public | consume verification token |
| POST | `/auth/login` | public | sets `ce_session` HttpOnly cookie |
| POST | `/auth/logout` | cookie | revoke session, clear cookie |
| GET | `/auth/me` | cookie | current user |
| POST | `/auth/profile` | cookie | update first/last name |
| POST | `/auth/request-password-reset` | public | email a reset link |
| POST | `/auth/reset-password` | public | set new password; kills all sessions |
| GET | `/member/dashboard` | cookie | member landing data |
| POST | `/membership-applications` | public | join form |
| POST | `/contact-submissions` | public | contact form |
| POST | `/newsletter-subscriptions` | public | newsletter form |
| POST | `/payments/initialize` | public | Paystack checkout URL |
| GET | `/payments/verify/{reference}` | public | confirm a transaction |
| GET | `/admin/overview` | admin cookie | counts |
| GET | `/admin/membership-applications` | admin cookie | latest 100 |
| GET | `/admin/contact-submissions` | admin cookie | latest 100 |
| GET | `/admin/newsletter-subscribers` | admin cookie | latest 100 |
| POST | `/admin/users/grant-admin` | admin cookie | promote an existing account |

**There is no API documentation endpoint, no OpenAPI UI, and no API versioning.** Adding a
route means adding it to this single file and to this table.

### The `email_sent` contract

`send_email()` returns `True` only when the message was handed to the SMTP server. Configuration
is read at import time by `os.getenv`, after `load_dotenv()` reads `back_end/.env`; real
environment variables win over the file. That value is surfaced to clients so a user is never
told "check your inbox" when nothing was sent:

- `POST /auth/register` → `email_sent` on the response.
- `POST /membership-applications`, `/contact-submissions`, `/newsletter-subscriptions` →
  `email_sent` alongside `message`. (The newsletter's already-subscribed early return reports
  `false`: that path sends nothing.)
- `GET /health` → `mail_configured`, a **global** flag mirroring `payments_configured`.

**Never add a per-request `email_sent` to `/auth/request-email-verification` or
`/auth/request-password-reset`.** A non-existent address never triggers a send, so the flag
would differ by account existence and reintroduce enumeration (§6 item 4). Both routes call the
send helper and *deliberately discard* the result — there is a comment at each site saying so.
Do not "fix" that by returning it.

### Data model

`User`, `EmailVerificationToken`, `PasswordResetToken`, `UserSession`, `MembershipApplication`,
`ContactSubmission`, `NewsletterSubscriber`, `Payment`.

Schema is created by `Base.metadata.create_all()` at startup. There is **no migration tool**.
Adding a column to an existing table requires a hand-written `ALTER TABLE` in the `lifespan`
handler — see the `is_admin` example at `back_end.py:485-496`. That approach does not scale; if
you need a second one, propose real migrations rather than adding another branch.

---

## 5. Never guess

This is the single most important behavioural rule in this repository.

**Stop and ask** when a task requires:

- A price, tier name, or membership benefit
- A claim about legal status, tax deductibility, insurance, or coverage
- A response-time or support promise
- Contact details, addresses, names, or photographs of real people
- A privacy-policy or terms-of-use change
- Anything about whether the organisation may legally collect, hold, or transfer a given field

Publish **placeholder-free-marked** content instead of plausible-sounding invented content.
Where sample text exists today it is visibly sample ("Replace or expand this with your
organization's full statement of faith"), and that marker must survive until a human supplies
the real text.

Inventing a legal claim — even a hedged, reasonable-sounding one — is a worse outcome than an
obvious placeholder.

---

## 6. Security and privacy invariants

These are load-bearing. Each is currently true; each has a comment or structure preserving it.
**Do not regress any of them**, and do not remove the reasoning comments.

1. **No credential or session token in browser storage.** Sessions are the HttpOnly
   `ce_session` cookie. Never move a token into `localStorage`/`sessionStorage`, never render
   one into HTML, never read one in JavaScript.
2. **Never process card details, passwords, or membership data in client-side JavaScript.**
   Payments are redirected to Paystack's hosted checkout. There is no card field anywhere and
   there must not be.
3. **Login runs a dummy password verify for unknown emails** (`back_end.py:1047-1054`) so that
   response timing cannot be used to enumerate accounts. Preserve this on any refactor of login.
4. **Unknown-email endpoints return an identical response.** `/auth/request-email-verification`
   and `/auth/request-password-reset` both return the same message whether or not the account
   exists. Do not add "no account with that email" errors.
5. **Email must be verified before login.** Unverified accounts get `403`, not a session.
6. **Tokens are stored hashed, single-use, and expiring.** Verification and reset tokens are
   SHA-256 hashed at rest, marked `used_at` on first use, and expire in one hour.
7. **Requesting a new verification token invalidates older unused ones** (`back_end.py:275-280`).
8. **Changing a password invalidates every existing session** for that user
   (`back_end.py:986-988`). A password reset must never leave an attacker's session alive.
9. **Passwords are Argon2-hashed** via `PasswordHash.recommended()`. Never add a second
   hashing path, never compare passwords with `==`.
10. **Payment success requires an amount, currency, and reference match** against the stored
    record (`back_end.py:634-639`). Never trust a status flag alone.
11. **`PAYMENTS_ENABLED` defaults to `false`** and returns `503` when off. Do not flip it, and
    do not remove the switch. README §Configuration explains the three preconditions.
12. **CORS is closed in production.** `ENVIRONMENT=production` permits only `FRONTEND_BASE_URL`
    and only `GET`/`POST` with a `Content-Type` header. The permissive localhost regex is
    development-only. Never widen it "temporarily".
13. **Security headers are set by middleware** — `X-Content-Type-Options`, `X-Frame-Options`,
    `Referrer-Policy`, `Permissions-Policy`, and HSTS in production. Add to this list; never
    bypass the middleware.
14. **Cookie flags:** `httponly=True`, `samesite="lax"`, `secure=` true in production. Preserve
    all three.
15. **Secrets live in the environment only.** `.env` is gitignored and `.env.example` is
    committed with placeholder values. Never commit a real key, password, SMTP credential, or
    the SQLite database. If you need a new setting, add it to `.env.example` as a placeholder
    *and* to README §Configuration.
16. **No third-party scripts, fonts, or CDNs.** Every asset is served locally. Adding a remote
    `<script>` or `<link>` is a supply-chain and privacy decision requiring explicit approval.
17. **Admin routes re-check the session server-side** via `require_admin()`. Hidden UI is never
    authorization.

### Privacy of member data

Do not log request bodies, email addresses, passwords, or tokens. Do not expose member data in
error messages. Admin tables render subscriber data — that data stays behind the admin check.

---

## 7. Working on the backend

One file. Some rules that keep it workable:

- **Keep the layering implicit but consistent:** Pydantic request models near the top, ORM
  models below them, helpers after, then routes. A new route goes with the other routes.
- **Business rules do not belong in route bodies.** The membership tier allow-list, the price
  table, and the tier→price lookup are duplicated in several places (see §9). Extending them
  makes the duplication worse — check with the owner before adding a fourth copy.
- **Keep Pydantic validation in the models**, not as manual `if` checks in the handler.
  Field constraints (`min_length`, `max_length`, `EmailStr`, `pattern`, `ge`) are the pattern.
  Password minimum is 12 characters and is enforced in the model.
- **One SQLAlchemy session per request** via `with SessionLocal() as session:`. Do not hold a
  session across a network call if you can avoid it.
- **Sending email must never fail a request.** `send_email()` catches and prints. Form data is
  saved first, email is best-effort second. Keep that order.
- **Admin notifications go through `send_admin_notification(subject, what_happened, name, email)`.**
  It carries the submitter's name and email but never their message text, and every caller
  discards its result. Adding a parameter for message text is a privacy decision (§6), not a
  convenience — the signature is the safeguard. It replaces what used to be three hand-written
  `send_email(ADMIN_NOTIFICATION_EMAIL, …)` blocks; do not reintroduce a fourth.
- **Normalise email to lowercase** before storing or comparing — every existing handler does.
- **Timezone-aware UTC** for every timestamp (`now_utc()`). SQLite returns naive datetimes, so
  existing code defensively re-attaches `timezone.utc` before comparing. Follow that pattern.

---

## 8. Frontend conventions

### Page skeleton

Every page is a standalone HTML file. There is no templating and no shared partial — **the
header and footer are duplicated byte-for-byte in every page.** That is the current design. If
you change the nav or footer, you are changing ~22 files, and you must change all of them.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Name | Christian Educators Global Network</title>
    <meta name="description" content="…">   <!-- required on every page -->
    <link rel="icon" type="image/svg+xml" href="…/assets/img/favicon.svg">
    <link rel="stylesheet" href="…/assets/css/style.css">
</head>
<body>
    <header class="site-nav">
        <a class="nav-wordmark" href="…/index.html">…</a>
        <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="nav-menu">☰<span class="visually-hidden">Menu</span></button>
        <nav id="nav-menu" class="nav-links" aria-label="Main navigation">
            … six primary links …
            <span class="nav-actions">
                <a class="nav-login" href="…/member-login.html" data-nav-portal>Member Login</a>
                <a class="nav-donate" href="…/donate.html">Donate</a>
            </span>
        </nav>
    </header>
    <main> … </main>
    <footer class="site-footer"> … three .footer-col navs + .footer-legal … </footer>
    <script src="…/assets/js/main.js"></script>
</body>
</html>
```

**Path rule:** `index.html` and `404.html` sit at the root and use root-relative paths
(`assets/…`, `pages/…`). Everything in `pages/` uses `../` paths. Getting this wrong is the most
common way to break a page. `main.js` handles the distinction internally via `IN_PAGES` and
`portalPath()`.

### Required per-page elements

Every page must keep: a unique `<title>`, a `<meta name="description">`, the viewport meta, an
`<svg>` favicon link, exactly one `<h1>`, `alt` text on every image, and a `<label>` bound to
every form input. The historical audit in `readme` verified all 17 pages for these; preserve the
standard when adding pages. Admin pages additionally carry `<meta name="robots" content="noindex">`.

### How JavaScript binds to markup

`main.js` is a single IIFE with no exports. Pages opt in by including the hooks below. A
dashboard page sets `hidden` on its `<main>` and lets the script reveal it only after auth
succeeds — so an unauthenticated visitor never sees the protected shell flash.

| Hook | Effect |
|---|---|
| `[data-year]` | filled with the current year |
| `[data-go-back]` | suppresses the auto-injected "← Back" button on `<main>` |
| `[data-nav-portal]` | rewritten to "My Dashboard" when signed in |
| `[data-nav-admin]`, `[data-admin-link]` | unhidden for admins |
| `[data-logout="target.html"]` | POSTs `/auth/logout`, then navigates |
| `[data-member-dashboard]` | gate: redirects to login unless authenticated |
| `[data-member-name]`, `[data-member-email]`, `[data-member-status]` | filled from `/member/dashboard` |
| `[data-admin-dashboard]` | gate: `401`→member dashboard, `403`→access-denied notice |
| `[data-admin-access-error]`, `[data-admin-applications\|contacts\|subscribers]` | admin counts |
| `[data-email-verification]`, `[data-verification-status\|error\|login]` | verify-email page |
| `[data-payment-result]`, `[data-payment-status\|error]` | reads `?reference=` and verifies |
| `[data-go-back]`, `.nav-toggle`, `.nav-links a` | back button, mobile menu, active-link marking |

### Form conventions

Forms are identified by **`id`**, and `main.js` binds a specific handler per id. There is no
generic form binder — adding a form means adding a block to `main.js`.

| Form id | Endpoint |
|---|---|
| `join-form` | `/membership-applications` |
| `contact-form` | `/contact-submissions` |
| `newsletter-form` | `/newsletter-subscriptions` |
| `login-form` | `/auth/login` |
| `create-account-form` | `/auth/register` |
| `request-password-reset-form`, `reset-password-form` | `/auth/request-password-reset`, `/auth/reset-password` |
| `grant-admin-form` | `/admin/users/grant-admin` |
| `donate-form` | `/payments/initialize` (disabled in markup) |

House style for a form: `<form id="…" novalidate>`, an error `<p class="form-error" hidden>` and
a `div.form-success` with an id passed to the handler, a `reportValidity()` guard before
submitting, `credentials: "include"` on every request (handled by `apiRequest`), and the
success element revealed while the form is `hidden` on success. Copy an existing form exactly.

**A send failure is surfaced, not hidden.** The three public forms also carry a sibling
`<div class="form-error" id="…-warning" hidden>` — `#join-warning`, `#contact-warning`,
`#newsletter-warning` — and the register flow carries `#create-account-warning`
(`pages/member-login.html`). `connectPublicForm()` takes a `warningId` and reveals that panel
instead of the success panel when the response reports `email_sent === false`. The warning copy
must say the record **was** saved and the email **was not** sent; it must not imply the
submission failed. See §4 for why the two auth resend routes are excluded from this.

**`novalidate` is deliberate.** Validation is driven by `reportValidity()` in JS so the custom
error elements are used consistently. Do not remove it without replacing that mechanism.

### CSS

One stylesheet, `assets/css/style.css`, no preprocessor, no CSS modules. It uses semantic
section classes (`.content-section`, `.soft-section`, `.warm-section`, `.dark-section`,
`.page-hero`, `.info-grid`, `.form-panel`, `.dash-card`, `.tier-card`, `.action-button`).
Reuse these rather than adding new ones or inline styles. A few inline styles already exist in
the page bodies; **do not add more** — extend the stylesheet instead.

---

## 9. Known debt and launch blockers

Verified against the code on 2026-09-23. This is not a wish list — every item is a real defect
or a real gap.

### Blockers (must be resolved before real users)

1. **No Paystack webhook.** There is no `/payments/webhook` route. A payment's status becomes
   `success` **only** when the buyer's browser loads `payment-result.html` and calls
   `/payments/verify/{reference}`. If the buyer closes the tab after paying, the record sits at
   `pending` forever and no membership is fulfilled. README §Configuration makes "webhooks have
   been verified" a precondition for enabling payments, so this must be built — with signature
   verification — before `PAYMENTS_ENABLED` is ever set to true.
2. **Placeholder content is live.** Testimonials, articles, events, impact figures, and
   "coming soon" copy are all samples. Some carry visible notes (e.g. `about.html` asks to
   "Replace or expand this with your organization's full statement of faith"), most do not.
3. **Unverified legal claims appear on every page.** The footer of all ~22 pages asserts
   *"Christian Educators Global Network is a 501(c)(3) Religious Non-Profit"*. Membership tier
   cards promise "professional-consultation coverage", "No-cost term life insurance benefit",
   and "priority responses". Privacy policy and terms of use are drafted but unreviewed. **No
   agent may edit these to be more specific or more reassuring.** An authorised representative
   supplies the approved wording.
4. **Pricing is duplicated in three places** and will drift: the `membership_prices` dict
   (`back_end.py:559-564`), the tier cards in `pages/membership.html`, and the radio values in
   `pages/join.html`. A change to one silently leaves the others wrong. Fixing this is a
   worthwhile early task — but note that tier allow-lists differ between the application
   endpoint (`gift`, `unsure` accepted) and the payment endpoint (priced tiers only), which is
   correct and must be preserved.

### Significant gaps

5. **Test coverage is minimal.** A pytest harness now exists at `back_end/tests/`, guarding the
   `.env`-loading regression (`test_env_loading.py`, three tests). **Every security invariant in
   §6 is still unprotected by tests**, and there is no CI. Treat the harness as a starting point,
   not as coverage. Run it with `cd back_end && uv run pytest tests/ -q`.
6. **No rate limiting** on login, registration, password-reset requests, or the public forms.
   Login has a timing defence but nothing against brute force or form spam.
7. **No data-export or account-deletion path**, although the privacy policy promises users may
   "request access to, correction of, or deletion of" their information.
8. **PostgreSQL is still not usable.** `DATABASE_URL` is now read from the environment
   (`back_end.py:50`), and the engine no longer assumes SQLite when it is built
   (`engine_options()`, `back_end.py:64`). Two blockers remain, and neither is solved by
   configuration: **no PostgreSQL driver is installed**, and the startup compatibility check
   in `lifespan` uses SQLite-only `PRAGMA table_info` syntax (`back_end.py:589`). Both belong
   with item 9 — a migration tool is the natural place to fix the second one.
9. **No migration system.** See §4.
10. **Email failures surface to the user; admin notifications are the remaining gap.** A failed
    send returns `False`, and the four client-facing flows (register, membership, contact,
    newsletter) show a warning panel instead of a false "check your inbox".
    - **A failed admin notification is still silent.** `send_admin_notification()`'s result is
      discarded by design — the submitter must not be told that our internal notification
      failed — so a failed admin email is lost with no record anywhere.
    - **No retry and no queue.** A transient relay outage loses the message permanently.
    - **No rate limiting on `/auth/register`** (item 6), so registrations can be scripted to
      generate one admin email each. The three public forms already had this exposure; adding
      registration widened it.
    - **Admin notifications carry the name, not the message.** Deliberate:
      `send_admin_notification()` takes no parameter for message text, so a contact
      submission's prayer request or job dispute stays behind the admin login instead of
      sitting in an inbox. The cost is that acting on a notification still means opening the
      dashboard.
11. **No admin audit log.** `grant-admin` and every read of member data go unrecorded.
12. **A compiled bytecode file is committed to git**: `back_end/__pycache__/back_end.cpython-314.pyc`.
    `back_end/.gitignore` covers `__pycache__/`, but the file was tracked before the rule
    existed. Removing it needs `git rm --cached` and is a deliberate, user-approved change (§12).
13. **Root `pyproject.toml` and `src/` are unused scaffolding** (§3). Harmless now; confusing
    later.
14. **No `robots.txt`, `sitemap.xml`, or Open Graph metadata.** README's checklist wants these
    at the final domain.
15. **No automated checks** — HTML validation, link checking, accessibility, or mobile testing.
    The `readme` audit performed these by hand once; nothing keeps them true.

---

## 10. Engineering discipline

Adapted from the practices that worked in this project's history. The backend was built one
coherent slice at a time (public forms → auth → admin → payments) and each slice was manually
exercised end to end. That is the standard to keep.

### Test first

There is currently no test suite, so "write the test first" sometimes means **building the
test harness itself first**. When you add the first tests, that harness is the feature.

Once a harness exists, for any new behaviour:

1. State the requirement, in one sentence, in terms of observable behaviour.
2. Write the test.
3. Run it. **Confirm it fails, and fails for the expected reason.**
4. Implement the smallest change that makes it pass.
5. Run it again. Confirm it passes.
6. Run the whole suite. Confirm nothing else broke.
7. Only then is the feature complete.

Never write production code first and invent tests afterwards.

### One feature at a time

Do not bundle unrelated changes. Do not refactor while implementing a feature. If you notice
something else worth fixing, **write it down and finish the current task** — then raise it.

### Minimal implementation

Implement only what the current requirement demands. Do not build for hypothetical
requirements, do not introduce abstractions for a second caller that does not exist, do not
add a dependency to satisfy a test. If a task looks like it needs a framework, that is a signal
to stop and discuss, not to install one.

### No feature creep

If a request falls outside the current work — a new integration, a redesign, a new service —
say so and stop. Do not implement it silently because it seemed adjacent.

### Honest reporting

Show failures. Do not weaken an assertion to get a green run. Do not delete a failing test.
Do not report "done" for something you did not run. Do not describe a step as verified when
you only reasoned about it. When something is unverified, say *unverified*. When a task is
blocked, say exactly what blocks it.

### Debugging

When something fails: read the actual failure, identify the violated expectation, trace it, and
decide whether the fault is in the test, the implementation, or your understanding of the
requirement. **Fix the smallest correct layer.** Do not rewrite large sections to make a
symptom disappear.

### Explaining your work

Do not dump large blocks of unexplained code. For non-trivial changes, prefer explaining the
problem and the approach *before* the diff, and keep the explanation proportionate to the
change. For security-relevant work (§6), explain the mechanism, not just the edit — the reading
of whoever edits next is currently the only thing protecting these invariants.

If the developer asks for a deeper walkthrough or a Socratic, one-concept-at-a-time approach,
use hint escalation rather than a complete solution: guiding question → small hint → stronger
hint → partial solution → full solution.

---

## 11. Git discipline

Commit messages in this repository's history are uninformative (`"CEGNP"`, repeated). Improve
that going forward: describe what changed and why, in the imperative.

**Do not run destructive git commands** unless the developer explicitly asks and understands
the consequence:

```bash
git reset --hard
git clean -fd
git checkout -- .
git rm --cached …     # §9 item 12 — ask first
```

Prefer observable commands:

```bash
git status
git diff
git log --oneline -5
```

If you are on `main`, branch before committing. Commit or push only when asked. Never commit
`.env`, a real credential, or the database file — if a diff contains one, stop and say so.

---

## 12. Definition of done

A change is done when all of the following hold:

- The requirement is stated in one sentence.
- The behaviour was **verified by running it** — a test, or a demonstrated request/response.
- Existing behaviour was not broken.
- No section §6 invariant was weakened.
- No §5 guess was made: any unknown was raised rather than invented.
- No secret, credential, or member datum was added to the repository.
- New configuration, if any, appears in `.env.example` (as a placeholder) **and** in README.
- The change is described honestly, including anything left unverified.

Report in this shape:

```text
Change:
  <one line>

Requirement:
  <the observable behaviour this delivers>

Verified by:
  <command run / test name — and its actual result>

Files changed:
  <paths>

Invariants checked:
  <which §6 items apply, and how they were preserved>

Left unverified / open:
  <anything you did not confirm, or "none">
```

---

## 13. When requirements are missing

This repository has no product spec. Behaviour that is not already in the code is a **decision
owned by the organisation**, not by an agent.

When a task needs a decision the code does not already make, respond with:

```text
Document A / the code says:  X
This task requires:          Y
I cannot determine Y from the repository.

Options:
  1. …
  2. …

Which do you want?
```

Do not pick one and proceed. Do not implement the most plausible option and mention it in
passing. Do not encode a guess in a default value, a placeholder price, or a comment.

The categories that most often trigger this are listed in §5. When in doubt, they apply.

---

## 14. CLI interaction protocol

The developer works through the terminal and copies commands you provide.

- **Give one atomic step at a time.** Do not hand over a batch of commands and ask for
  everything at once.
- **Give exact commands**, including `mkdir -p` for new directories. Never assume a directory
  or file exists — check first.
- **Inspect before overwriting.** Run `cat` or `sed -n '1,120p'` on an existing file before
  proposing a change to it, and never blind-overwrite.
- **Stop after each step** and wait for the real terminal output. A command having been
  *provided* is not evidence it *succeeded*.
- **Never assume** "file created", "test passed", or "server started" without observed output.
  The developer's terminal output is the confirmation.

If a single atomic change genuinely needs several shell lines, provide those together and say
so explicitly.

---

## 15. The rules that matter most

> **Never invent what the organisation has not supplied.** Prices, legal status, coverage
> promises, and privacy wording come from an authorised human — not from a plausible guess.

> **Never weaken a §6 invariant to make a task easier.**

> **Never process a card, a password, or a member record in browser JavaScript.**

> **Do not report a step as verified unless you observed it.**

> **One atomic change at a time. Show the command. Wait for the output.**
