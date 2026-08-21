# Day 21: Stripe Integration & Real Payments

Turns the Day 20 manual-approval queue into **real payments** for the Pro
plan, using Stripe Checkout + a webhook. Free stays free, Enterprise stays
"contact us" — only Pro gets a real card charge.

## Why there are TWO apps now

Streamlit Community Cloud only serves the Streamlit UI itself — it can't
expose a raw `POST` endpoint that Stripe can sign-verify and hit directly.
So payments now involve two small pieces:

| Piece | Where it runs | Job |
|---|---|---|
| `chatbot.py` (+ `stripe_service.py`) | Streamlit Cloud (unchanged) | Creates a Stripe Checkout Session when a user clicks **Pay with Stripe**, sends them to Stripe's hosted payment page. |
| `stripe_webhook.py` (+ `stripe_service.py`) | **New, separate** host — Render/Railway/Fly.io free tier | Receives the `checkout.session.completed` event *after* Stripe actually charges the card, verifies it's really from Stripe, and upgrades the user's plan. |

Both processes import the same `stripe_service.py` and talk to the **same
Turso database**, so a plan upgrade made by the webhook shows up in the
Streamlit app immediately — no polling, no sync job.

## New/changed files

| File | Change |
|---|---|
| `stripe_service.py` | **New.** Secret loading (Streamlit secrets → env var fallback, same pattern `database.py` uses for Turso), `create_checkout_session()`, `handle_checkout_completed()`. |
| `stripe_webhook.py` | **New.** Standalone Flask app — one route, one job: verify + handle the webhook. Full deploy steps are in the file's header comment. |
| `requirements-stripe.txt` | **New.** Deps for the separate webhook host only (flask, gunicorn, stripe, libsql) — don't add this to Streamlit Cloud. |
| `requirements.txt` | Added `stripe` (needed by `chatbot.py` to create Checkout Sessions). |
| `chatbot.py` | Pricing page: when Stripe is configured, the Pro card shows **💳 Pay with Stripe** instead of **Request Pro**, and reads `?checkout=success`/`cancelled` from the URL to show a confirmation. |

## Fallback behavior (important)

`stripe_service.is_configured()` checks whether `STRIPE_SECRET_KEY` and
`STRIPE_PRICE_ID_PRO` are set. **Until you finish the Stripe setup below,
the app behaves exactly like Day 20** — manual admin-approval queue, no
button changes. Nothing breaks in the meantime.

## Setup checklist

1. **Stripe Dashboard → Product catalog** — create a "Pro" product with a
   recurring ₹499/mo price. Copy its price ID (`price_...`).
2. **Deploy `stripe_webhook.py`** to Render (or similar) — see the deploy
   steps in that file's header. You'll get a public URL like
   `https://your-app.onrender.com`.
3. **Stripe Dashboard → Developers → Webhooks → Add destination**
   - Events from: **Your account** (not "Connected accounts" — that's for
     Stripe Connect/marketplace platforms, not a plan subscription app)
   - Endpoint URL: `https://your-app.onrender.com/webhook/stripe`
   - Events to send: `checkout.session.completed`
   - Copy the signing secret (`whsec_...`) it gives you afterward.
4. **Set secrets in both places:**
   - Streamlit Cloud secrets: `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID_PRO`
   - Render environment variables: `TURSO_DATABASE_URL`, `TURSO_AUTH_TOKEN`,
     `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_ID_PRO`
5. Test with a Stripe **test-mode** card (`4242 4242 4242 4242`, any future
   date/CVC) before flipping to live keys.

## Known limitations (honest list)

- No subscription-cancel/downgrade UI yet — cancelling a Pro subscription
  in the Stripe customer portal won't yet downgrade `users.plan` back to
  Free (needs a `customer.subscription.deleted` handler — good Day 24
  candidate: "Refunds & Cancellations").
- No invoice/receipt emailing — Stripe sends its own receipt, but nothing
  hits `email_service.py` yet.
- Enterprise is still "contact us" by design — no self-serve checkout for it.
- The Render free tier spins down after inactivity, so the very first
  webhook after idle time may be a few seconds slower (cold start).

## Coming next (Day 22)

Invoice generation & PDF reports for completed payments.
