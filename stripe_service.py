# ============================================
# Day 21: stripe_service.py  (NEW FILE)
# Real Stripe Checkout for the Pro plan.
#
# Falls back to the Day 20 manual admin-approval flow (pricing.py)
# automatically whenever Stripe keys aren't configured — so this is safe
# to deploy before you've finished Stripe setup. Once STRIPE_SECRET_KEY +
# STRIPE_PRICE_ID_PRO are set, is_configured() flips to True and the
# Pricing page in chatbot.py switches to a real "Pay with Stripe" button.
#
# Shared by TWO processes:
#   1. chatbot.py (Streamlit)  -> create_checkout_session()
#   2. stripe_webhook.py (Flask, deployed separately) -> handle_checkout_completed()
# Both talk to the SAME Turso database via database.get_connection(), so
# a plan upgrade made here shows up in the Streamlit app immediately.
# ============================================

import os


def _get_secret(name):
    """Reads a secret from Streamlit secrets when running under Streamlit,
    or from an environment variable otherwise (stripe_webhook.py, a plain
    Flask process, has no Streamlit runtime at all)."""
    try:
        import streamlit as st
        val = st.secrets.get(name)
        if val:
            return val
    except Exception:
        pass
    return os.getenv(name)


def get_stripe_keys():
    return {
        "secret_key": _get_secret("STRIPE_SECRET_KEY"),
        "webhook_secret": _get_secret("STRIPE_WEBHOOK_SECRET"),
        "price_id_pro": _get_secret("STRIPE_PRICE_ID_PRO"),
        "app_url": _get_secret("STREAMLIT_APP_URL") or "https://murthu-ai-chatbot.streamlit.app/",
    }


def is_configured():
    """True once real Stripe keys + a Pro price ID are set. Until then the
    Pricing page keeps using the Day 20 manual-approval queue."""
    keys = get_stripe_keys()
    return bool(keys["secret_key"] and keys["price_id_pro"])


def create_checkout_session(user_id, plan_key):
    """Creates a Stripe Checkout Session for the given plan and returns the
    URL to send the user to. Returns None if Stripe isn't configured, or
    the plan has no price attached (Enterprise stays 'contact us')."""
    keys = get_stripe_keys()
    if plan_key != "pro" or not keys["secret_key"] or not keys["price_id_pro"]:
        return None

    import stripe
    stripe.api_key = keys["secret_key"]

    app_url = keys["app_url"].rstrip("/")
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": keys["price_id_pro"], "quantity": 1}],
        success_url=f"{app_url}/?checkout=success",
        cancel_url=f"{app_url}/?checkout=cancelled",
        client_reference_id=str(user_id),
        metadata={"user_id": str(user_id), "plan": plan_key},
    )
    return session.url


def handle_checkout_completed(session):
    """Called by stripe_webhook.py when a checkout.session.completed event
    arrives. Upgrades the user's plan for real and clears any matching
    pending Day-20 upgrade_request so the Admin queue doesn't show a stale
    row for a plan that's already been paid for."""
    metadata = session.get("metadata") or {}
    user_id = metadata.get("user_id") or session.get("client_reference_id")
    plan = metadata.get("plan")
    if not user_id or not plan:
        return False

    user_id = int(user_id)

    import admin_service
    admin_service.set_user_plan(user_id, plan)

    from database import get_connection
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE upgrade_requests SET status='approved', resolved_at=CURRENT_TIMESTAMP "
        "WHERE user_id = ? AND status='pending'",
        (user_id,),
    )
    conn.commit()
    conn.close()

    try:
        import pricing
        pricing.get_pending_requests.clear()
    except Exception:
        pass  # running outside Streamlit — no cache to clear

    # Day 22: record the payment + mint an invoice. This runs inside the
    # separate Flask webhook process (no Streamlit runtime), which is
    # exactly why invoice_service only touches database.py directly and
    # never imports streamlit itself.
    import invoice_service
    amount_info = session.get("amount_total")  # Stripe sends this in the
    # smallest currency unit; fall back to the configured price if a test
    # event doesn't include it.
    amount = (amount_info / 100) if amount_info else 499
    invoice_service.record_payment(
        user_id=user_id,
        gateway="stripe",
        plan=plan,
        amount=amount,
        currency=(session.get("currency") or "inr").upper(),
        gateway_order_id=session.get("id"),
        gateway_payment_id=session.get("payment_intent") or session.get("id"),
        status="paid",
    )

    return True
