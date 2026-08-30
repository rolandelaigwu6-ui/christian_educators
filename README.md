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

Copy `back_end/.env.example` into a private local environment or set the listed variables in the terminal before starting the API. Never commit real API keys, SMTP keys, passwords, or the SQLite database.

`PAYMENTS_ENABLED` is deliberately `false`. Do not enable it until the organisation's Paystack account is approved, the public domain is live over HTTPS, and Paystack webhooks have been verified.

## Launch checklist

- Supply verified organisation name, contact details, domain, legal status, privacy terms, and membership-benefit wording.
- Replace all sample testimonials, articles, events, impact statements, and placeholder contact information.
- Verify the production sending domain in Brevo using SPF/DKIM records.
- Deploy the frontend and API using HTTPS, a managed database, backups, and a secrets manager.
- In production, put the API behind the same HTTPS domain (or a trusted reverse proxy) so the frontend can use same-origin `/auth` and `/admin` requests.
- Restrict CORS to the production frontend URL and remove local-development origins.
- Configure the organisation's Paystack Live account, webhook URL, and Live Secret Key only on the production host.
- Review legal claims, data-retention practice, tax language, and consent wording with the organisation's authorised representative.
