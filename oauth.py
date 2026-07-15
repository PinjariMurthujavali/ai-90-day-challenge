# ============================================
# Day 14: oauth.py
# Google OAuth2 login ("Sign in with Google"), sitting next to the
# existing username/password auth in auth.py rather than replacing it.
#
# Flow (standard OAuth2 Authorization Code flow):
#   1. build_google_auth_url() -> user clicks it, goes to Google
#   2. Google redirects back to our app with ?code=...&state=...
#   3. exchange_code_for_token() swaps that code for an access token
#   4. fetch_google_userinfo() gets {email, name, sub} from Google
#   5. login_or_create_oauth_user() finds/creates the local user row
#      and hands back a user_id, same as auth.login_user() does.
#
# Setup (add to .env / Streamlit secrets):
#   GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
#   GOOGLE_CLIENT_SECRET=xxxx
#   GOOGLE_REDIRECT_URI=https://your-app-url/         (must match Google
#                                                        Cloud Console exactly)
# ============================================

import os
import secrets

import requests

from database import get_connection

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"


def _get_secret(name):
    """Reads from Streamlit secrets first (deployed app), falls back to
    plain environment variables (local dev / the Flask API scripts)."""
    try:
        import streamlit as st
        val = st.secrets.get(name)
        if val:
            return val
    except Exception:
        pass
    return os.getenv(name)


def is_google_oauth_configured():
    return bool(_get_secret("GOOGLE_CLIENT_ID") and _get_secret("GOOGLE_CLIENT_SECRET"))


def build_google_auth_url(redirect_uri, state=None):
    """Returns (url, state). Pass the same `state` back in on the callback
    to protect against CSRF - store it in st.session_state before redirecting."""
    client_id = _get_secret("GOOGLE_CLIENT_ID")
    if not client_id:
        raise RuntimeError("GOOGLE_CLIENT_ID is not configured.")

    state = state or secrets.token_urlsafe(16)
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    query = "&".join(f"{k}={requests.utils.quote(str(v), safe='')}" for k, v in params.items())
    return f"{GOOGLE_AUTH_ENDPOINT}?{query}", state


def exchange_code_for_token(code, redirect_uri):
    """Swaps the one-time ?code=... from Google for an access token."""
    client_id = _get_secret("GOOGLE_CLIENT_ID")
    client_secret = _get_secret("GOOGLE_CLIENT_SECRET")

    resp = requests.post(
        GOOGLE_TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def fetch_google_userinfo(access_token):
    """Returns {'sub', 'email', 'name', 'picture', ...} for the logged-in Google account."""
    resp = requests.get(
        GOOGLE_USERINFO_ENDPOINT,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


def get_user_by_oauth(provider, oauth_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, username FROM users WHERE oauth_provider = ? AND oauth_id = ?",
        (provider, oauth_id),
    )
    row = cursor.fetchone()
    conn.close()
    return row


def _username_available(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row is None


def _make_unique_username(base):
    """Google gives us an email like 'jane.doe@gmail.com' - turn that into a
    clean username, adding a numeric suffix only if it's already taken."""
    base = (base.split("@")[0] or "user").replace(".", "_").replace(" ", "_").strip() or "user"
    if _username_available(base):
        return base
    for i in range(1, 1000):
        candidate = f"{base}{i}"
        if _username_available(candidate):
            return candidate
    return f"{base}{secrets.token_hex(3)}"


def login_or_create_oauth_user(provider, oauth_id, email, name, avatar_url=None):
    """Finds the local user linked to this Google account, or creates one
    on first login. Returns (user_id, username)."""
    existing = get_user_by_oauth(provider, oauth_id)
    if existing:
        return existing[0], existing[1]

    username = _make_unique_username(name or email or "user")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO users (username, password_hash, email, oauth_provider, oauth_id, avatar_url)
           VALUES (?, NULL, ?, ?, ?, ?)''',
        (username, email, provider, oauth_id, avatar_url),
    )
    conn.commit()
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    user_id = cursor.fetchone()[0]
    conn.close()
    return user_id, username
