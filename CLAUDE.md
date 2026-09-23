# Christian Educators Global Network — working rules

Full detail: @Agent.md

This repository is a **static HTML frontend + a single-file FastAPI backend** for a nonprofit
membership organisation. It is *not* the SoTeach Go tutoring project.

```text
pages/*.html + assets/       static frontend, no build step, no framework
back_end/back_end.py         the entire backend, ~1200 lines, one file
back_end/.env.example        committed template; .env is gitignored
```

## Hard rules

1. **Never invent what the organisation has not supplied.** Prices, legal status (501(c)(3)),
   coverage/insurance promises, response times, contact details, and privacy wording come from
   an authorised human. Placeholders stay visibly marked. Flagging an unknown is always better
   than a plausible guess — see Agent.md §5 and §13.
2. **Never weaken a security invariant** (Agent.md §6). In particular: no token or credential in
   browser storage; no card/password/member data in client-side JS; unknown-email endpoints stay
   identical; password change kills all sessions; `PAYMENTS_ENABLED` stays `false`.
3. **Never commit a secret, `.env`, a credential, or the SQLite database.**
4. **Verify by running.** Do not report a step as done unless you observed its output.
5. **One atomic change at a time.** Give the exact command, then stop and wait for the terminal
   output. Do not batch commands.
6. **Inspect before overwriting** — `cat` or `sed -n '1,120p'` first.
7. **No destructive git** (`reset --hard`, `clean -fd`, `checkout -- .`, `rm --cached`) without
   an explicit, informed request.
8. **No new dependency, framework, build step, or CDN script** without approval.
9. **No tests exist yet.** Building the test harness is itself a legitimate first task. Test
   first once a harness exists; never write production code and backfill tests.
10. **No feature creep.** If a request is outside the current task, name it and stop.

## Things that will bite you

- The HTML pages are not templated — the header and footer are duplicated
  **byte-for-byte in ~22 HTML files**. Any nav/footer change touches all of them. See
  Agent.md §8.
- `index.html` and `404.html` use root-relative asset paths (`assets/…`); everything in
  `pages/` uses `../`. Mixing them breaks the page.
- The `readme` file (no extension) is an **outdated** audit. Its claim that `main.js` does demo
  auth with `localStorage` is false — that was fixed. Verify its findings against the code.
- The root `pyproject.toml` and `src/` are unused `uv init` scaffolding. The real metadata is
  `back_end/pyproject.toml`.
- Membership prices are duplicated in three places and will drift (Agent.md §9 item 4).
- **There is no Paystack webhook.** Payments only confirm when the buyer's browser returns to
  `payment-result.html`. See Agent.md §9 item 1 — this blocks enabling payments.

## Definition of done

Requirement stated → behaviour verified by running it → nothing else broken → no invariant
weakened → no guess made → report honestly, including what was left unverified. Format:
Agent.md §12.

## CLI protocol

Exact command. One step. Then wait for output. Agent.md §14.
