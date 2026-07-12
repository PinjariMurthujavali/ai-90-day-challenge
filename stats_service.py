# ============================================
# stats_service.py
# Site-wide "how many people visited" + "how many clicks"
# counters. Stored permanently in the site_stats table so
# the numbers survive app restarts/redeploys.
#
# UPDATED: these getters were being called unconditionally on
# EVERY Streamlit rerun (i.e. every single click, by every user)
# — 3 extra network round-trips to the remote Turso database on
# every interaction, which is the main reason the app felt slow.
# These numbers don't need to be split-second accurate, so they
# are now cached for a few seconds with st.cache_data — this
# alone removes most of the per-click network delay.
# ============================================

import streamlit as st

from database import get_connection


def _get(stat_key):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT stat_value FROM site_stats WHERE stat_key = ?", (stat_key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0


def _increment(stat_key, by=1):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE site_stats SET stat_value = stat_value + ? WHERE stat_key = ?",
        (by, stat_key),
    )
    conn.commit()
    conn.close()


def record_visit():
    """Call once per new browser session (a real 'new visitor' load)."""
    _increment("total_visits")
    get_total_visits.clear()


def record_click():
    """Call on every button/interaction rerun to track overall activity."""
    _increment("total_clicks")


@st.cache_data(ttl=20)
def get_total_visits():
    return _get("total_visits")


@st.cache_data(ttl=20)
def get_total_clicks():
    return _get("total_clicks")


@st.cache_data(ttl=20)
def get_total_registered_users():
    """Total number of people who have ever registered (permanent count)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count
