# Christian Educators Global Network

## Local development

Start the frontend from the project root:

```powershell
uv run python -m http.server 5500 --bind 127.0.0.1
```

In another terminal, start the API:

```powershell
cd back_end
uv run uvicorn back_end:app --reload --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:5500`.

## Configuration

Backend settings come from two places, in this order:

1. **Real environment variables** — anything exported in the shell wins.
2. **`back_end/.env`** — created by copying `back_end/.env.example`. It is read
   automatically at startup and is gitignored.

```bash
cp back_end/.env.example back_end/.env
```

Never commit real API keys, SMTP keys, passwords, or the SQLite database.

### Email

Email is sent through Brevo's SMTP relay. **Until `SMTP_HOST` and `SMTP_FROM_EMAIL` are
both set, no email is sent at all** — each message is printed to the backend terminal
instead. `GET /health` reports `"mail_configured": false` in that state, so check it first
if mail is not arriving.

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

**Setting it to a PostgreSQL URL does not work on its own yet.** Three things are missing:

1. No PostgreSQL driver is installed. Add `psycopg[binary]` to `back_end/pyproject.toml`.
2. The startup compatibility check in the `lifespan` handler uses `PRAGMA table_info`,
   which is SQLite-only syntax and fails against PostgreSQL.
3. There is no migration tool — schema changes are hand-written `ALTER TABLE` statements.

Items 2 and 3 are best resolved together, by adopting a migration tool.

### Payments

`PAYMENTS_ENABLED` is deliberately `false`. Do not enable it until the organisation's Paystack account is approved, the public domain is live over HTTPS, and Paystack webhooks have been verified.

## Launch checklist

- Supply verified organisation name, contact details, domain, legal status, privacy terms, and membership-benefit wording.
- Replace all sample testimonials, articles, events, impact statements, and placeholder contact information.
- Verify the production sending domain in Brevo using SPF/DKIM records.
- Deploy the frontend and API using HTTPS, a managed database, backups, and a secrets manager. A PostgreSQL driver and a migration tool are prerequisites — see Configuration → Database.
- In production, put the API behind the same HTTPS domain (or a trusted reverse proxy) so the frontend can use same-origin `/auth` and `/admin` requests.
- Restrict CORS to the production frontend URL and remove local-development origins.
- Configure the organisation's Paystack Live account, webhook URL, and Live Secret Key only on the production host.
- Review legal claims, data-retention practice, tax language, and consent wording with the organisation's authorised representative.
