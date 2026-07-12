# ============================================
# profile_stats.py
# "Profile views" feature: every time someone opens a public
# profile via its shareable link, we log ONE view (permanently,
# in the profile_views table) along with where the click came
# from (WhatsApp, Instagram, Google, Direct, etc). Only the
# profile owner sees the numbers.
# ============================================

from database import get_connection


# Known referrer domains -> a friendly source label
_SOURCE_MAP = {
    "whatsapp.com": "WhatsApp",
    "wa.me": "WhatsApp",
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "l.instagram.com": "Instagram",
    "twitter.com": "Twitter / X",
    "x.com": "Twitter / X",
    "t.co": "Twitter / X",
    "linkedin.com": "LinkedIn",
    "telegram.org": "Telegram",
    "t.me": "Telegram",
    "google.com": "Google Search",
    "youtube.com": "YouTube",
    "reddit.com": "Reddit",
}


def detect_source(referer_url):
    """Turn a raw Referer header into a friendly source label."""
    if not referer_url:
        return "Direct"
    referer_url = referer_url.lower()
    for domain, label in _SOURCE_MAP.items():
        if domain in referer_url:
            return label
    # same-site navigation (clicked around inside the app itself)
    if "streamlit.app" in referer_url:
        return "In-app"
    return "Other link"


def record_profile_view(profile_username, source):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO profile_views (profile_username, source) VALUES (?, ?)",
        (profile_username, source),
    )
    conn.commit()
    conn.close()


def get_total_views(profile_username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM profile_views WHERE profile_username = ?",
        (profile_username,),
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_views_by_source(profile_username):
    """Returns [(source, count), ...] sorted by most clicks first."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT source, COUNT(*) as cnt
        FROM profile_views
        WHERE profile_username = ?
        GROUP BY source
        ORDER BY cnt DESC
    ''', (profile_username,))
    rows = cursor.fetchall()
    conn.close()
    return rows
