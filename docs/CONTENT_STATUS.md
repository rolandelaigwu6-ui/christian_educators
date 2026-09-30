# COCEGN blueprint implementation

Source: the supplied September 2026 Website Blueprint and Website Copy v3, read in full. Organisation details were confirmed by the user. Document suggestions were treated as requirements to assess, not instructions to purchase services, publish private data, create accounts or announce a launch.

## Implemented

- Homepage with educator/supporter routes, two pillars, registration, Academy, salary support and State Coordinator callout.
- Founder story and biography, supplied mission and vision, CAC RC 1546376 / 2018, current local reach and global growth plan.
- Programs, Academy, child sponsorship, teacher salary support, widow support, Ministry to the Aged, getting involved and State Coordinator pages.
- Bronze, Silver, Gold and Diamond applications. Phone, location, role, school/organisation, optional church affiliation, values agreement, application consent and optional updates are saved. No unconfirmed fees are charged.
- Coordinator, volunteer/companion, partnership and teacher-story forms feed the private admin contact inbox with labelled topics. Support buttons preselect the appropriate contact topic. These are enquiries, not automatic sponsorship assignments or event registrations.
- Events/media, honest pending podcast/event states, newsletter and teacher-story submissions. The Academy and founder stories are linked as real supplied content.
- Current phone/WhatsApp: +234 803 287 2739. Old flyer number removed. The street address remains omitted following the user's earlier instruction; Otukpo registration and Ohimini active area are explained without claiming a physical office.
- Six labelled illustrative photo sets, responsive sizes, lazy loading and replacement instructions in PHOTO_REPLACEMENT.md. No fabricated beneficiary cards or founder photograph.
- Shared navigation and footer, mobile layouts, keyboard focus, current-section navigation, local metadata, noindex on account pages, robots file and domain-dependent sitemap generator.
- Old sample testimonials, prices, fabricated calendar entries and insurance/coverage claims removed from the public pages. Existing account/session protections retained.

## Needed to finish the content-dependent features

- Exact tier fees, eligibility and benefits. The documents still use `[Fill in]`; approval of the documents does not provide those amounts.
- Verified bank details, approved payment account and working payment webhook before checkout. Monthly giving currently opens an enquiry, not an automatic recurring charge.
- Actual beneficiary information, guardian/adult consent and agreed support costs before individual galleries, profiles and Birthday Diary entries can be published.
- Actual photos, founder portrait, certificate scan, approved impact figures and testimonials. The website does not invent these.
- Dated event details and podcast hosting links; the present event cards are program descriptions with date enquiries, not a bookable calendar.
- New domain, official email and social accounts. The suggested domain and handles in the blueprint were not claimed or registered.
- Full organisation-reviewed retention, privacy, membership and giving terms. Current policy pages describe the implemented site and identify review gaps; they do not assert tax deductibility or insurance.

## Deployment and editorial tools

The project remains static HTML/CSS/JavaScript plus FastAPI. No WordPress migration, third-party analytics, remote font, paid service or new production dependency was introduced. Admins can review enquiries; a content-editing CMS is a separate future implementation.

Only public HTML, `assets/`, `404.html`, `robots.txt` and the generated sitemap should be deployed to the static host. Do not publish the repository root wholesale: `back_end/`, `.git/`, `.env`, databases, tests and documents must stay private. robots.txt is not access control.

After a real domain is chosen, run:

```bash
python3 scripts/generate_sitemap.py --base-url https://YOUR-CONFIRMED-DOMAIN
```

Then add its absolute URL as a `Sitemap:` line in robots.txt and submit it to Search Console. Backend SMTP delivery, production hosting, payment verification/webhooks and deployment remain launch tasks, not completed by this content upgrade.

## Data compatibility

The `membership_application_profiles` companion table stores additional application fields and the values agreement. A separate `membership_application_consents` table records application consent, keeping it distinct from optional news subscriptions. The existing `membership_applications` table and old application records are preserved. `create_all` creates the new tables on restart; no columns are added to an existing table. Existing legacy clients remain accepted, but no old sample membership price can reach checkout. Back up the database before production updates.
