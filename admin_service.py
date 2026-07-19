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
