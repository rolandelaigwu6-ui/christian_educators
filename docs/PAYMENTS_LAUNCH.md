# Donation and payment readiness

Checked 15 October 2026 at https://cocegn.vercel.app.

## Can a visitor send money now?

No website checkout is available. The live health endpoint reports
`payments_configured: false` and `payments_enabled: false`; a valid donation
initialization request returns 503. The giving page states that online giving is
unavailable and publishes no bank account. It offers WhatsApp/contact enquiries.
This does not establish whether an organisation bank account can independently
receive transfers; no receiving account has been verified for publication.

The owner confirms a Paystack account exists but is not activated. Logging into
the dashboard does not activate payments. Paystack must review the actual
business information and approve the receiving account.

## Activation work

1. Open Paystack's Compliance/Activate Business page. Use the actual legal
   registration type and name from the organisation's documents. Do not infer
   the registration type from the website's description alone.
2. Complete the sections requested for that registration type. The account
   owner supplies identity documents, any required identity verification,
   registration documents, addresses and declarations directly to Paystack.
   Do not put BVN/NIN, documents, API keys or passwords in project files/chat.
3. For a registered business, Paystack requires a corporate settlement bank
   account matching its business registration. Confirm the displayed account
   name and bank with the organisation before submitting.
4. Use the live website URL https://cocegn.vercel.app and the actual contact
   details. Resolve any policy/terms requirements with approved wording. The
   present policy pages still disclose organisation-review gaps.
5. Submit the completed application and wait for Paystack's approval. Do not
   promise an activation time or claim that test-mode payments are real funds.

## Technical checks before enabling donations

- Configure the correct **test** webhook in the test account settings and
  verify a provider-originated test payment through an isolated test deployment
  and database. The local tests use fixtures, not the Paystack sandbox.
- Callback: `https://cocegn.vercel.app/pages/payment-result.html`.
- Production webhook: `https://cocegn.vercel.app/payments/webhook`.
  Configure the matching environment's URL in Paystack Settings → API Keys &
  Webhooks. Never attach test checkout to production member/payment records.
- Keep the secret key server-side. The production application must reject a test
  key. Do not expose keys in JavaScript or commit environment files.
- Signed `charge.success` notifications validate the exact raw body with
  HMAC-SHA512, reference, integer amount and currency, then commit the known
  payment before acknowledging it. Duplicates preserve the first settlement;
  unknown account transactions do not create website records.
- Check the private administrator payment list and reconcile its reference,
  amount and status with Paystack. A successful charge is different from a
  completed payout to the settlement bank account.
- Finish the donation checkout UI only after the intended giving/payment
  arrangements are confirmed; currently the public page deliberately remains
  enquiry-only. Monthly giving is not a recurring charge implementation.
- After approval, configure the live key privately, enable donations, make an
  explicitly approved small live payment and confirm both payment recording
  and the payout destination/status. No live money test has been performed.
- Membership charges stay disabled until the organisation supplies approved
  fees and tier arrangements. Enabling donations must not charge sample fees.

## Other outstanding launch work

| Item | Current evidence / next step |
| --- | --- |
| Email | Brevo requests blocked by provider Cloudflare 1010; provider resolution needed. No inbox delivery proven. |
| Administrator | Approved email configured; real registration, verification and live admin acceptance remain incomplete. |
| Public forms | Seven controlled submissions persisted in PostgreSQL; admin visibility and removal of only those fixtures remain pending. |
| Database operations | Migration and manual backup/restore verified; scheduled backups, retention and responsible operator still need confirmation. |
| DBeaver | Installed with a memory cap; private read-only profile prepared, GUI/JDBC connection unverified. |
| Policies | Organisation must approve retention, privacy, membership/giving wording and the unsubscribe/deletion procedure. |
| Membership | Interest applications work; approvals, entitlements and private resource library are not implemented. |
| Content | Actual event dates, podcast links, consented photos and confirmed tier details still require supplied information. |

Sources: [Paystack activation](https://support.paystack.com/en/articles/2125506),
[Nigeria requirements](https://support.paystack.com/en/articles/2123970),
[webhooks](https://paystack.com/docs/payments/webhooks/),
[verification](https://paystack.com/docs/payments/verify-payments/).

## Implementation verification

The payment safeguards and private administrator table are deployed in production
(`dpl_J4JKm4tREAAFEGvx526jUEvoUAmL`), with checkout still disabled. Backend:
75 tests passed, including disposable real PostgreSQL account journeys. Browser:
627 assertions passed, including payment table rendering, escaped references and
phone/tablet/desktop layouts with mocked data. Static checks: 30 pages passed.
No real Paystack sandbox or live transaction has been processed.
