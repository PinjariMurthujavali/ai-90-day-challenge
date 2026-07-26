# ============================================
# Day 18: admin_service.py  (NEW FILE)
# Backs the Admin panel: every registered user with their chat/message
# counts, current plan, and admin flag — plus the write actions an
# admin can take (change plan, promote/demote admin, reset a user's
# password). Kept separate from auth.py, which only handles the
# logged-in user's own identity.
# ============================================

import streamlit as st

from database import get_connection
import auth


PLAN_OPTIONS = ["free", "pro", "enterprise"]


@st.cache_data(ttl=10)
def list_users_with_stats():
    """One row per user: identity + plan + live usage counts, for the
    admin table. Cached briefly — admin actions below explicitly clear
    this cache so changes show up immediately after a save."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT
            u.id,
            u.username,
            u.email,
            u.plan,
            u.is_admin,
            u.oauth_provider,
            u.created_at,
            COUNT(DISTINCT c.id)  AS total_chats,
            COUNT(DISTINCT m.id)  AS total_messages,
            COUNT(DISTINCT CASE WHEN c.is_public = 1 THEN c.id END) AS public_chats
        FROM users u
        LEFT JOIN chats c ON c.user_id = u.id
        LEFT JOIN messages m ON m.chat_id = c.id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return rows


@st.cache_data(ttl=15)
def get_platform_totals():
    """Top-line numbers for the admin dashboard header."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT plan, COUNT(*) FROM users GROUP BY plan")
    by_plan = dict(cursor.fetchall())

    cursor.execute("SELECT COUNT(*) FROM chats")
    total_chats = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM messages")
    total_messages = cursor.fetchone()[0]

    conn.close()
    return {
        "total_users": total_users,
        "by_plan": by_plan,
        "total_chats": total_chats,
        "total_messages": total_messages,
    }


# ============================================
# Day 25: Payment Analytics & Revenue Tracking
# Reads straight from the `payments` table Day 21-24 already write real
# rows into (Stripe/Razorpay charges + refunds) — this is actual money
# that moved, not projected/estimated figures.
# ============================================

@st.cache_data(ttl=30)
def get_revenue_summary():
    conn = get_connection()
    cursor = conn.cursor()

    # Gross = every payment that was ever actually collected, whether or
    # not it was later refunded — a refund is money going back OUT, it
    # doesn't erase the fact the charge happened. Filtering to only
    # status='paid' here would silently shrink "gross" every time a
    # refund got approved (caught this while testing: refunding a
    # payment made gross_revenue drop by the refunded amount too, which
    # is a real reporting bug — net_revenue is where a refund should
    # show up, not gross).
    cursor.execute("SELECT COALESCE(SUM(amount), 0) FROM payments WHERE status IN ('paid', 'refunded')")
    gross_revenue = cursor.fetchone()[0]

    cursor.execute("SELECT COALESCE(SUM(refunded_amount), 0) FROM payments WHERE refund_status = 'approved'")
    total_refunded = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM payments WHERE status IN ('paid', 'refunded')")
    paid_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM payments WHERE refund_status = 'approved'")
    refund_count = cursor.fetchone()[0]

    cursor.execute("SELECT gateway, COALESCE(SUM(amount), 0), COUNT(*) FROM payments WHERE status IN ('paid', 'refunded') GROUP BY gateway")
    by_gateway = cursor.fetchall()

    cursor.execute("SELECT plan, COALESCE(SUM(amount), 0), COUNT(*) FROM payments WHERE status IN ('paid', 'refunded') GROUP BY plan")
    by_plan_revenue = cursor.fetchall()

    # Active paying subscribers right now (used as a simple MRR proxy —
    # count of currently-active pro/enterprise plans times their price is
    # a reasonable stand-in for real recurring-billing MRR, which would
    # need the payment gateway's subscription objects to compute exactly).
    cursor.execute("SELECT plan, COUNT(*) FROM users WHERE plan != 'free' GROUP BY plan")
    active_paid_by_plan = dict(cursor.fetchall())

    conn.close()

    net_revenue = gross_revenue - total_refunded
    avg_order_value = (gross_revenue / paid_count) if paid_count else 0

    return {
        "gross_revenue": gross_revenue,
        "total_refunded": total_refunded,
        "net_revenue": net_revenue,
        "paid_count": paid_count,
        "refund_count": refund_count,
        "avg_order_value": avg_order_value,
        "refund_rate": (refund_count / paid_count * 100) if paid_count else 0,
        "by_gateway": by_gateway,
        "by_plan_revenue": by_plan_revenue,
        "active_paid_by_plan": active_paid_by_plan,
    }


@st.cache_data(ttl=30)
def get_daily_revenue(days=30):
    """Revenue per day for the last N days — feeds the trend chart on
    the admin Revenue tab."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DATE(created_at) as day, COALESCE(SUM(amount), 0)
        FROM payments
        WHERE status IN ('paid', 'refunded') AND created_at >= DATE('now', ?)
        GROUP BY DATE(created_at)
        ORDER BY day ASC
    ''', (f'-{days} days',))
    rows = cursor.fetchall()
    conn.close()
    return rows


def set_user_plan(user_id, plan):
    if plan not in PLAN_OPTIONS:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET plan = ?, plan_updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (plan, user_id),
    )
    conn.commit()
    conn.close()
    list_users_with_stats.clear()
    get_platform_totals.clear()
    return True


def set_user_admin(user_id, is_admin_flag, requesting_user_id):
    """Prevents an admin from removing their own last-admin access by
    accident — at least one admin account must always remain."""
    conn = get_connection()
    cursor = conn.cursor()

    if not is_admin_flag:
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = 1")
        admin_count = cursor.fetchone()[0]
        if admin_count <= 1:
            conn.close()
            return False, "Can't remove the last remaining admin."

    cursor.execute("UPDATE users SET is_admin = ? WHERE id = ?",
                   (1 if is_admin_flag else 0, user_id))
    conn.commit()
    conn.close()
    list_users_with_stats.clear()
    return True, "Updated."


def reset_user_password(user_id, new_password):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (auth.hash_password(new_password), user_id),
    )
    conn.commit()
    conn.close()
