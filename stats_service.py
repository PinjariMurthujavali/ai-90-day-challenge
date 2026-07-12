# ============================================
# stats_service.py
# Site-wide "how many people visited" + "how many clicks"
# counters. Stored permanently in the site_stats table so
# the numbers survive app restarts/redeploys.
# ============================================

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


def record_click():
    """Call on every button/interaction rerun to track overall activity."""
    _increment("total_clicks")


def get_total_visits():
    return _get("total_visits")


def get_total_clicks():
    return _get("total_clicks")
