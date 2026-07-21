# ============================================
# Day 20: pricing.py  (NEW FILE)
# Plan catalog + the upgrade-request flow. Deliberately does NOT simulate
# a real charge — no Stripe keys are configured for this project yet, and
# faking a "payment successful" message would be actively misleading.
# Instead: a logged-in user requests a plan, it lands in a queue, and an
# admin approves it from the Admin panel (Day 18), which sets users.plan.
# When real Stripe checkout is wired in later, only create_request()'s
# caller changes (checkout success webhook instead of a button click) —
# the request/approve data model underneath stays the same.
# ============================================

import streamlit as st

from database import get_connection

PLANS = {
    "free": {
        "label": "Free",
        "price": "₹0/mo",
        "tagline": "Get started with the basics",
        "features": [
            "Unlimited chats with any AI personality",
            "Publish chats to the community",
            "In-app notifications",
        ],
    },
    "pro": {
        "label": "Pro",
        "price": "₹499/mo",
        "tagline": "For regular builders and creators",
        "features": [
            "Everything in Free",
            "Email notifications",
            "Priority AI response speed",
            "File attachments up to 3MB",
        ],
    },
    "enterprise": {
        "label": "Enterprise",
        "price": "Contact us",
        "tagline": "For teams and organizations",
        "features": [
            "Everything in Pro",
            "Admin-managed team accounts",
            "Dedicated support",
        ],
    },
}


def create_upgrade_request(user_id, requested_plan):
    if requested_plan not in PLANS:
        return False, "Unknown plan."

    conn = get_connection()
    cursor = conn.cursor()

    # Don't stack duplicate pending requests for the same user.
    cursor.execute(
        "SELECT id FROM upgrade_requests WHERE user_id = ? AND status = 'pending'",
        (user_id,),
    )
    if cursor.fetchone():
        conn.close()
        return False, "You already have a pending request — an admin will review it soon."

    cursor.execute(
        "INSERT INTO upgrade_requests (user_id, requested_plan) VALUES (?, ?)",
        (user_id, requested_plan),
    )
    conn.commit()
    conn.close()
    get_pending_requests.clear()
    return True, "Request submitted! An admin will review it shortly."


@st.cache_data(ttl=10)
def get_pending_requests():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ur.id, u.username, ur.requested_plan, ur.created_at, u.id
        FROM upgrade_requests ur
        JOIN users u ON u.id = ur.user_id
        WHERE ur.status = 'pending'
        ORDER BY ur.created_at ASC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows


def resolve_request(request_id, approve):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE upgrade_requests SET status = ?, resolved_at = CURRENT_TIMESTAMP WHERE id = ?",
        ("approved" if approve else "rejected", request_id),
    )
    conn.commit()
    conn.close()
    get_pending_requests.clear()


def get_user_pending_request(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT requested_plan FROM upgrade_requests WHERE user_id = ? AND status = 'pending'",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None
