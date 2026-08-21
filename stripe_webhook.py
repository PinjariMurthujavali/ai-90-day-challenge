# ============================================
# Day 21: stripe_webhook.py  (NEW FILE — standalone service)
# A tiny Flask app whose ONLY job is to receive Stripe webhook events.
#
# WHY THIS IS A SEPARATE APP FROM THE STREAMLIT UI:
# Streamlit Community Cloud only serves the Streamlit page itself — it
# doesn't expose a raw HTTP POST route that Stripe can sign-verify and
# hit directly. So this small Flask service gets deployed SEPARATELY
# (Render / Railway / Fly.io free tier all work) with its own public
# HTTPS URL, and THAT url + "/webhook/stripe" is what goes into the
# Stripe Dashboard's "Endpoint URL" field — not the streamlit.app URL.
#
# It shares the SAME Turso database as the Streamlit app (same
# TURSO_DATABASE_URL / TURSO_AUTH_TOKEN env vars), so a plan upgrade made
# here shows up in the Streamlit app immediately, no polling needed.
#
# ---------------------------------------------------------------
# DEPLOY (Render.com free tier, ~5 min):
#   1. New -> Web Service -> connect this GitHub repo
#   2. Build command:  pip install -r requirements-stripe.txt
#   3. Start command:  gunicorn stripe_webhook:app
#   4. Environment variables (Render dashboard -> Environment):
#        TURSO_DATABASE_URL      (same value as Streamlit secrets)
#        TURSO_AUTH_TOKEN        (same value as Streamlit secrets)
#        STRIPE_SECRET_KEY       (Stripe Dashboard -> Developers -> API keys)
#        STRIPE_WEBHOOK_SECRET   (filled in AFTER step 6 below)
#        STRIPE_PRICE_ID_PRO     (Stripe Dashboard -> Product catalog -> Pro price)
#   5. Deploy. Copy the Render URL, e.g. https://murthu-stripe-webhook.onrender.com
#   6. In Stripe Dashboard -> Developers -> Webhooks -> Add destination:
#        Events from:   Your account   (NOT "Connected accounts")
#        Endpoint URL:  https://murthu-stripe-webhook.onrender.com/webhook/stripe
#        Events to send: checkout.session.completed
#      Stripe shows a "Signing secret" (starts with whsec_) after creating
#      it — paste that into STRIPE_WEBHOOK_SECRET on Render and redeploy.
# ---------------------------------------------------------------

from flask import Flask, request, jsonify
import stripe

import stripe_service

app = Flask(__name__)


@app.route("/webhook/stripe", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    keys = stripe_service.get_stripe_keys()

    if not keys["webhook_secret"]:
        return jsonify({"error": "STRIPE_WEBHOOK_SECRET not configured"}), 500

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, keys["webhook_secret"])
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        stripe_service.handle_checkout_completed(session)

    # Return 200 for any other event type too — Stripe retries aggressively
    # on non-2xx responses, and we simply don't act on events we don't handle.
    return jsonify({"received": True}), 200


@app.route("/", methods=["GET"])
def health():
    """Simple health check so Render's uptime check (and you) can confirm
    the service is alive without hitting the real webhook route."""
    return jsonify({"status": "ok", "service": "stripe-webhook-receiver"}), 200


if __name__ == "__main__":
    # Local testing only. In production, Render runs this via gunicorn
    # (see the Start command above), not this __main__ block.
    app.run(port=5001)
