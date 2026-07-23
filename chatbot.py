# ============================================
# Day 10: Notifications + Public Profiles
# Multi-user AI chatbot — built on Day 9 community foundation
#
# NEW today:
#   - 🔔 Notification bell: get pinged when someone likes or
#     comments on one of your public chats, with an unread badge
#   - 👤 Public profile pages: click any author's name in Explore
#     to see everything they've published to the community
#   - New notification_service.py module (kept separate so the
#     "who gets notified about what" logic doesn't bloat social_service.py)
# ============================================

import streamlit as st
from streamlit_autorefresh import st_autorefresh
import pandas as pd
from groq import Groq
from dotenv import load_dotenv
import os

from database import init_database
from styles import APP_CSS
from config import PERSONALITIES, personality_info, personality_label

import auth
import oauth
import email_service
import admin_service
import upload_service
import pricing
import chat_service as chats
import social_service as social
import notification_service as notify
import stats_service as stats
import profile_stats
from export_utils import export_chat_json, export_chat_pdf
import stripe_service
import razorpay_service
import invoice_service

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("⚠️ GROQ_API_KEY not found! Please set it in your .env file.")
    st.stop()

client = Groq(api_key=api_key)

init_database()
auth.ensure_admin_account()


# ============================================
# PAGE CONFIG + CSS
# ============================================

st.set_page_config(page_title="Murthu AI Chatbot", page_icon="🤖", layout="wide")
st.markdown(APP_CSS, unsafe_allow_html=True)

st.markdown('<p class="main-title">🤖 Murthu AI Chatbot</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-title">Search. Export. Analyze. Share. Your multi-user AI chat community, now with superpowers.</p>',
    unsafe_allow_html=True,
)
st.caption(f"👥 {stats.get_total_registered_users():,} registered  ·  👀 {stats.get_total_visits():,} visits  ·  🖱️ {stats.get_total_clicks():,} clicks")


# ============================================
# SESSION STATE
# ============================================

defaults = {
    "user_id": None,
    "username": None,
    "current_chat_id": None,
    "show_new_chat_form": False,
    "auth_view": "login",
    "prefill_username": "",
    "main_view": "chat",          # "chat" | "explore" | "analytics" | "profile" | "notifications"
    "explore_sort": "popular",    # "popular" | "recent"
    "explore_view_chat_id": None,
    "profile_username": None,
}
for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ---- NEW: permanent site-wide visit + click tracking ----
if "_visited" not in st.session_state:
    st.session_state._visited = True
    stats.record_visit()          # first script run in this browser session = 1 visit
else:
    stats.record_click()          # every rerun after that = a click/interaction

# ---- auto-login from a persistent session token in the URL ----
if not st.session_state.user_id:
    token = st.query_params.get("token")
    if token:
        user = auth.get_user_by_token(token)
        if user:
            st.session_state.user_id = user[0]
            st.session_state.username = user[1]

# ---- Day 14: Google OAuth2 callback (?code=...&state=...) ----
if not st.session_state.user_id:
    oauth_code = st.query_params.get("code")
    oauth_state = st.query_params.get("state")
    expected_state = st.session_state.get("_oauth_state")
    # Only block when we DID remember a state and it doesn't match (real
    # CSRF mismatch). If the round-trip to Google wiped session_state (the
    # usual reason "sign in" silently landed back on the login page),
    # expected_state is None here — still safe to proceed, since `code` is
    # a single-use token Google only just issued to this browser.
    state_ok = (expected_state is None) or (oauth_state == expected_state)
    already_processed = st.session_state.get("_oauth_code_seen") == oauth_code
    if oauth_code and state_ok and not already_processed:
        st.session_state["_oauth_code_seen"] = oauth_code
        try:
            get_redirect_uri = getattr(oauth, "get_configured_redirect_uri", None)
            if get_redirect_uri is None:
                raise RuntimeError(
                    "oauth module is out of date on this deployment "
                    "(missing get_configured_redirect_uri) — push oauth.py to "
                    "GitHub and reboot the app on Streamlit Cloud."
                )
            # Prefer the exact redirect_uri we used when building the Google
            # auth URL (saved in session_state) — this MUST match byte-for-byte
            # what Google issued the code for, or the token exchange 400s.
            redirect_uri = st.session_state.get("_oauth_redirect_uri") or get_redirect_uri()
            if not redirect_uri and hasattr(st, "context"):
                redirect_uri = st.context.headers.get("Origin", "")
            access_token = oauth.exchange_code_for_token(oauth_code, redirect_uri)
            info = oauth.fetch_google_userinfo(access_token)
            user_id, username = oauth.login_or_create_oauth_user(
                provider="google",
                oauth_id=info["sub"],
                email=info.get("email"),
                name=info.get("name") or info.get("email"),
                avatar_url=info.get("picture"),
            )
            st.session_state.user_id = user_id
            st.session_state.username = username
            token = auth.create_session(user_id)
            st.query_params.clear()
            st.query_params["token"] = token
            st.rerun()
        except Exception as e:
            st.error(f"❌ Google sign-in failed: {e}")

# ---- deep link: ?share=<token> opens a public chat straight into Explore ----
share_token_param = st.query_params.get("share")

# ---- deep link: ?profile=<username> opens someone's public profile directly ----
profile_param = st.query_params.get("profile")


# ============================================
# SMALL REUSABLE UI PIECES
# ============================================

def render_transcript_readonly(history, personality):
    p_info = personality_info(personality)
    for role, content in history:
        if role == "user":
            st.chat_message("user", avatar="🧑").write(content)
        else:
            st.chat_message("assistant", avatar=p_info["emoji"]).write(content)


def render_like_and_share(chat_id, share_token, key_prefix):
    like_col, share_col = st.columns([1, 2])

    with like_col:
        liked = social.has_liked(chat_id, st.session_state.user_id)
        count = social.get_like_count(chat_id)
        label = f"{'❤️' if liked else '🤍'} {count}"
        if st.button(label, key=f"{key_prefix}_like_{chat_id}", use_container_width=True):
            social.toggle_like(chat_id, st.session_state.user_id)
            st.rerun()

    with share_col:
        with st.popover("🔗 Share", use_container_width=True):
            st.caption("Copy this link — anyone can open it straight to this chat:")
            base_url = st.context.headers.get("Origin", "") if hasattr(st, "context") else ""
            share_url = f"?share={share_token}" if share_token else ""
            st.code(share_url or "Publish this chat first to get a link", language=None)
            st.caption("On the deployed app, prefix this with your app's URL.")


def render_comments(chat_id, key_prefix):
    st.markdown("##### 💬 Comments")
    comments = social.get_comments(chat_id)

    if not comments:
        st.caption("No comments yet — be the first to say something nice! 👀")
    else:
        for comment_id, commenter, content, created_at in comments:
            col1, col2 = st.columns([9, 1])
            with col1:
                st.markdown(
                    f'<div class="comment-box">'
                    f'<span class="comment-author">{commenter}</span>'
                    f'<span class="comment-time">{str(created_at)[:16]}</span>'
                    f'<div class="comment-content">{content}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with col2:
                if commenter == st.session_state.username:
                    if st.button("🗑️", key=f"{key_prefix}_delcomment_{comment_id}"):
                        social.delete_comment(comment_id, st.session_state.user_id)
                        st.rerun()

    with st.form(key=f"{key_prefix}_comment_form_{chat_id}", clear_on_submit=True):
        new_comment = st.text_input("Add a comment", placeholder="wow super! 🔥",
                                     label_visibility="collapsed")
        submitted = st.form_submit_button("Post comment", use_container_width=True)
        if submitted and new_comment.strip():
            social.add_comment(chat_id, st.session_state.user_id, new_comment)
            st.rerun()


def render_public_chat_viewer(chat_id, key_prefix="view"):
    """Full read-only view of a public chat: transcript + like + share + comments."""
    conn_row = social.get_chat_by_share_token  # not used directly here; fetch via chats
    history = chats.get_chat_history(chat_id)
    owner_id = chats.get_chat_owner(chat_id)
    owner_name = auth.get_username(owner_id)

    is_public, share_token = social.get_chat_public_info(chat_id)
    like_count = social.get_like_count(chat_id)
    comment_count = social.get_comment_count(chat_id)

    info_col, profile_col = st.columns([5, 1])
    with info_col:
        st.markdown(f"##### 👤 by **{owner_name}**  ·  ❤️ {like_count}  ·  💬 {comment_count}")
    with profile_col:
        if st.button("View profile →", key=f"{key_prefix}_toprofile_{chat_id}", use_container_width=True):
            st.session_state.profile_username = owner_name
            st.session_state.main_view = "profile"
            st.session_state.explore_view_chat_id = None
            st.rerun()
    st.write("---")

    render_transcript_readonly(history, "mentor")
    st.write("---")

    render_like_and_share(chat_id, share_token, key_prefix)
    st.write("")
    render_comments(chat_id, key_prefix)


# ============================================
# AUTHENTICATION SECTION
# ============================================
if not st.session_state.user_id:

    st.write("---")

    hero_col, form_col = st.columns([1, 1.05], gap="large")

    with hero_col:
        st.markdown("""
            <div class="auth-hero">
                <span class="auth-hero-badge">🚀 90-Day Build Challenge · Day 20</span>
                <div class="auth-floaters" aria-hidden="true">
                    <span class="floater f1">🤖</span>
                    <span class="floater f2">⚡</span>
                    <span class="floater f3">🔷</span>
                    <span class="floater f4">🛰️</span>
                    <span class="floater f5">🔶</span>
                    <span class="floater f6">✨</span>
                </div>
                <h2 class="auth-hero-title">One platform for every<br>AI conversation you have.</h2>
                <p class="auth-hero-sub">
                    Chat with focused AI personalities, attach files, publish your best threads
                    to the community, and manage it all from one clean dashboard.
                </p>
                <div class="auth-feature-row">
                    <div class="auth-feature">
                        <span class="auth-feature-icon">💬</span>
                        <div><strong>Multi-personality chat</strong><br>
                        <span class="auth-feature-sub">Mentor, coder, coach & more</span></div>
                    </div>
                    <div class="auth-feature">
                        <span class="auth-feature-icon">📎</span>
                        <div><strong>File attachments</strong><br>
                        <span class="auth-feature-sub">Images, PDFs, docs — right in chat</span></div>
                    </div>
                    <div class="auth-feature">
                        <span class="auth-feature-icon">🌍</span>
                        <div><strong>Public profiles</strong><br>
                        <span class="auth-feature-sub">Share your best chats</span></div>
                    </div>
                    <div class="auth-feature">
                        <span class="auth-feature-icon">🔔</span>
                        <div><strong>Real-time alerts</strong><br>
                        <span class="auth-feature-sub">In-app + email notifications</span></div>
                    </div>
                    <div class="auth-feature">
                        <span class="auth-feature-icon">💎</span>
                        <div><strong>Flexible plans</strong><br>
                        <span class="auth-feature-sub">Free, Pro & Enterprise tiers</span></div>
                    </div>
                    <div class="auth-feature">
                        <span class="auth-feature-icon">🔒</span>
                        <div><strong>Secure by default</strong><br>
                        <span class="auth-feature-sub">Hashed passwords + Google login</span></div>
                    </div>
                </div>
            </div>
        """, unsafe_allow_html=True)
        st.markdown(
            f'<div class="auth-trust-row">'
            f'<span>👥 <strong>{stats.get_total_registered_users():,}</strong> builders</span>'
            f'<span>👀 <strong>{stats.get_total_visits():,}</strong> visits</span>'
            f'<span>⚡ Free forever</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with form_col:
        toggle_col1, toggle_col2, _ = st.columns([1, 1, 2])
        with toggle_col1:
            if st.button("🔐 Login", use_container_width=True,
                          type="primary" if st.session_state.auth_view == "login" else "secondary"):
                st.session_state.auth_view = "login"
                st.rerun()
        with toggle_col2:
            if st.button("📝 Register", use_container_width=True,
                          type="primary" if st.session_state.auth_view == "register" else "secondary"):
                st.session_state.auth_view = "register"
                st.rerun()

        st.write("")

        if st.session_state.auth_view == "login":
            with st.container(border=True):
                st.subheader("🔐 Welcome back")
                with st.form("login_form"):
                    username = st.text_input("Username", value=st.session_state.prefill_username)
                    password = st.text_input("Password", type="password")
                    submitted = st.form_submit_button("Login →", use_container_width=True, type="primary")

                    if submitted:
                        success, user_id = auth.login_user(username, password)
                        if success:
                            st.session_state.user_id = user_id
                            st.session_state.username = username
                            st.session_state.prefill_username = ""
                            token = auth.create_session(user_id)
                            st.query_params["token"] = token
                            st.success("Login successful! Redirecting...")
                            st.rerun()
                        else:
                            st.error("❌ Invalid username or password.")

                st.caption("Don't have an account? Click **📝 Register** above.")

                if hasattr(oauth, "is_google_oauth_configured") and oauth.is_google_oauth_configured():
                    st.write("")
                    st.caption("— or —")
                    redirect_uri = getattr(oauth, "get_configured_redirect_uri", lambda: "")()
                    if not redirect_uri and hasattr(st, "context"):
                        redirect_uri = st.context.headers.get("Origin", "")
                    if redirect_uri:
                        auth_url, state = oauth.build_google_auth_url(redirect_uri)
                        st.session_state["_oauth_state"] = state
                        st.session_state["_oauth_redirect_uri"] = redirect_uri
                        st.link_button("🔵 Sign in with Google", auth_url, use_container_width=True)
                    else:
                        st.caption("⚠️ Google sign-in needs GOOGLE_REDIRECT_URI configured.")

        else:
            with st.container(border=True):
                st.subheader("📝 Create your account")
                with st.form("register_form", clear_on_submit=True):
                    new_username = st.text_input("Choose username")
                    new_password = st.text_input("Choose password", type="password")
                    confirm_password = st.text_input("Confirm password", type="password")
                    new_email = st.text_input(
                        "Email (optional)",
                        placeholder="you@example.com",
                        help="Add this to get email alerts when someone likes or comments on your chats. "
                             "You can also add or change it later from your Profile.",
                    )
                    submitted = st.form_submit_button("Create account →", use_container_width=True, type="primary")

                    if submitted:
                        if not new_username.strip():
                            st.error("Username cannot be empty!")
                        elif new_password != confirm_password:
                            st.error("❌ Passwords don't match!")
                        elif len(new_password) < 6:
                            st.error("❌ Password must be at least 6 characters!")
                        elif new_email.strip() and "@" not in new_email:
                            st.error("❌ That email address doesn't look right.")
                        else:
                            clean_email = new_email.strip() or None
                            success, message = auth.register_user(new_username, new_password, clean_email)
                            if success:
                                st.session_state["_reg_success"] = new_username
                                if clean_email and email_service.is_configured():
                                    email_service.send_welcome_email(clean_email, new_username)
                            elif message == "USERNAME_EXISTS":
                                st.session_state["_reg_duplicate"] = new_username
                            else:
                                st.error(f"❌ {message}")

                if st.session_state.get("_reg_success"):
                    uname = st.session_state["_reg_success"]
                    st.success(f"🎉 Account created for **{uname}**! You're ready to log in.")
                    st.balloons()
                    if st.button("→ Continue to Login", use_container_width=True, key="goto_login_success"):
                        st.session_state.prefill_username = uname
                        st.session_state.auth_view = "login"
                        del st.session_state["_reg_success"]
                        st.rerun()

                if st.session_state.get("_reg_duplicate"):
                    uname = st.session_state["_reg_duplicate"]
                    st.warning(f"⚠️ You already have an account with username **{uname}**!")
                    if st.button("→ Go to Login instead", use_container_width=True, key="goto_login_duplicate"):
                        st.session_state.prefill_username = uname
                        st.session_state.auth_view = "login"
                        del st.session_state["_reg_duplicate"]
                        st.rerun()

                # Same Google OAuth flow as the Login tab — for a Google
                # account that doesn't exist yet, it creates one on the
                # spot (see oauth.login_or_create_oauth_user), so one
                # button correctly serves as both "sign up" and "sign in".
                if hasattr(oauth, "is_google_oauth_configured") and oauth.is_google_oauth_configured():
                    st.write("")
                    st.caption("— or —")
                    redirect_uri = getattr(oauth, "get_configured_redirect_uri", lambda: "")()
                    if not redirect_uri and hasattr(st, "context"):
                        redirect_uri = st.context.headers.get("Origin", "")
                    if redirect_uri:
                        auth_url, state = oauth.build_google_auth_url(redirect_uri)
                        st.session_state["_oauth_state"] = state
                        st.session_state["_oauth_redirect_uri"] = redirect_uri
                        st.link_button("🔵 Sign up with Google", auth_url, use_container_width=True)


# ============================================
# MAIN APP (LOGGED IN)
# ============================================
else:
    # ---- deep link into a shared chat ----
    if share_token_param:
        shared = social.get_chat_by_share_token(share_token_param)
        if shared:
            st.session_state.main_view = "explore"
            st.session_state.explore_view_chat_id = shared[0]

    # ---- deep link into a shared profile (records a profile view + source) ----
    if profile_param:
        st.session_state.main_view = "profile"
        st.session_state.profile_username = profile_param
        counted = st.session_state.setdefault("_counted_profile_views", set())
        if profile_param not in counted and profile_param != st.session_state.username:
            referer = ""
            try:
                referer = st.context.headers.get("Referer", "") if hasattr(st, "context") else ""
            except Exception:
                referer = ""
            source = profile_stats.detect_source(referer)
            profile_stats.record_profile_view(profile_param, source)
            counted.add(profile_param)

    # ---- Day 16: real-time feel — auto-rerun the script every few seconds
    # while looking at Explore / Notifications, so new likes, comments and
    # alerts from other users show up without a manual refresh.
    #
    # FIX: "chat" was in this list originally, and it broke sending messages —
    # the AI reply call (client.chat.completions.create) can take longer than
    # one refresh tick, and the autorefresh-triggered rerun cancels that
    # in-flight run, so the reply never got saved/shown. Your own chat window
    # is single-user anyway (nothing external to "poll" while you're mid
    # conversation), so it doesn't need live-refresh — only Explore/Notifications do.
    live_views = ("explore", "notifications")
    is_live = st.session_state.main_view in live_views
    if is_live:
        st_autorefresh(interval=6000, key="live_refresh_tick")

    header_col1, header_col2 = st.columns([3, 1])
    with header_col1:
        avatar_url = auth.get_avatar_url(st.session_state.user_id)
        name_html = f'👋 Welcome, **{st.session_state.username}**'
        if is_live:
            name_html += '&nbsp;&nbsp;<span class="live-badge">🟢 Live</span>'
        if avatar_url:
            av_col, txt_col = st.columns([1, 9])
            with av_col:
                st.image(avatar_url, width=38)
            with txt_col:
                st.markdown(f"### {name_html}", unsafe_allow_html=True)
        else:
            st.markdown(f"### {name_html}", unsafe_allow_html=True)
    with header_col2:
        if st.button("🚪 Logout", use_container_width=True):
            token = st.query_params.get("token")
            if token:
                auth.delete_session(token)
            st.query_params.clear()
            st.session_state.user_id = None
            st.session_state.username = None
            st.session_state.current_chat_id = None
            st.rerun()

    # ---- top nav: Chats / Explore / Analytics / Notifications / My Profile / Pricing ----
    unread_count = notify.get_unread_count(st.session_state.user_id)
    is_admin_user = auth.is_admin(st.session_state.user_id)
    nav_widths = [1, 1, 1, 1, 1, 1, 1] if is_admin_user else [1, 1, 1, 1, 1, 1]
    nav_cols = st.columns(nav_widths)
    nav_col1, nav_col2, nav_col3, nav_col4, nav_col5, nav_col6 = nav_cols[0], nav_cols[1], nav_cols[2], nav_cols[3], nav_cols[4], nav_cols[5]
    with nav_col1:
        if st.button("💬 Chats", use_container_width=True,
                      type="primary" if st.session_state.main_view == "chat" else "secondary"):
            st.session_state.main_view = "chat"
            st.rerun()
    with nav_col2:
        if st.button("🌍 Explore", use_container_width=True,
                      type="primary" if st.session_state.main_view == "explore" else "secondary"):
            st.session_state.main_view = "explore"
            st.rerun()
    with nav_col3:
        if st.button("📊 Analytics", use_container_width=True,
                      type="primary" if st.session_state.main_view == "analytics" else "secondary"):
            st.session_state.main_view = "analytics"
            st.rerun()
    with nav_col4:
        bell_label = f"🔔 Alerts ({unread_count})" if unread_count else "🔔 Alerts"
        if st.button(bell_label, use_container_width=True,
                      type="primary" if st.session_state.main_view == "notifications" else "secondary"):
            st.session_state.main_view = "notifications"
            st.rerun()
    with nav_col5:
        if st.button("👤 My Profile", use_container_width=True,
                      type="primary" if st.session_state.main_view == "profile" else "secondary"):
            st.session_state.profile_username = st.session_state.username
            st.session_state.main_view = "profile"
            st.rerun()
    with nav_col6:
        if st.button("💎 Pricing", use_container_width=True,
                      type="primary" if st.session_state.main_view == "pricing" else "secondary"):
            st.session_state.main_view = "pricing"
            st.rerun()
    if is_admin_user:
        with nav_cols[6]:
            if st.button("🛡️ Admin", use_container_width=True,
                          type="primary" if st.session_state.main_view == "admin" else "secondary"):
                st.session_state.main_view = "admin"
                st.rerun()

    st.write("---")

    # ---------------- SIDEBAR (only meaningful for the Chat view) ----------------
    with st.sidebar:
        st.markdown("## 💬 Your Chats")

        search_query = st.text_input("🔍 Search chats & messages", placeholder="Type to search...")

        if st.button("➕ New Chat", use_container_width=True, type="primary"):
            st.session_state.show_new_chat_form = True

        if st.session_state.show_new_chat_form:
            with st.container(border=True):
                personality = st.selectbox(
                    "Choose personality",
                    list(PERSONALITIES.keys()),
                    format_func=lambda p: f"{PERSONALITIES[p]['emoji']} {p.replace('_', ' ').title()}",
                    key="new_chat_personality"
                )
                title = st.text_input("Chat title", placeholder="e.g. Python help", key="new_chat_title")

                form_col1, form_col2 = st.columns(2)
                with form_col1:
                    if st.button("✅ Create", key="create_chat_btn", use_container_width=True, type="primary"):
                        chat_id = chats.create_chat(st.session_state.user_id, title, personality)
                        st.session_state.current_chat_id = chat_id
                        st.session_state.show_new_chat_form = False
                        st.session_state.main_view = "chat"
                        st.rerun()
                with form_col2:
                    if st.button("❌ Cancel", key="cancel_chat_btn", use_container_width=True):
                        st.session_state.show_new_chat_form = False
                        st.rerun()

        st.write("---")

        if search_query:
            results = chats.search_messages(st.session_state.user_id, search_query)
            seen_chats = set()
            unique_matches = []
            for chat_id, title, personality, content, role in results:
                if chat_id not in seen_chats:
                    seen_chats.add(chat_id)
                    unique_matches.append((chat_id, title, personality, content))

            st.caption(f"🔎 {len(unique_matches)} chat(s) match \"{search_query}\"")

            for chat_id, title, personality, content in unique_matches:
                p_info = personality_info(personality)
                with st.container(border=True):
                    if st.button(f"{p_info['emoji']} {title or 'Untitled'}",
                                  key=f"search_{chat_id}", use_container_width=True):
                        st.session_state.current_chat_id = chat_id
                        st.session_state.main_view = "chat"
                        st.rerun()
                    snippet = content[:80] + ("..." if len(content) > 80 else "")
                    st.caption(f"💬 {snippet}")

        else:
            user_chats = chats.get_user_chats(st.session_state.user_id)

            if not user_chats:
                st.caption("No chats yet. Create one above! 👆")

            for chat_id, title, personality, created_at, is_public in user_chats:
                p_info = personality_info(personality)
                is_active = st.session_state.current_chat_id == chat_id

                with st.container(border=True):
                    row_col1, row_col2 = st.columns([4, 1])
                    with row_col1:
                        label = f"{p_info['emoji']} {title or 'Untitled'}"
                        if st.button(label, key=f"chat_{chat_id}", use_container_width=True,
                                      type="primary" if is_active else "secondary"):
                            st.session_state.current_chat_id = chat_id
                            st.session_state.main_view = "chat"
                            st.rerun()
                        badges = (
                            f'<span class="badge" style="background:{p_info["color"]}">'
                            f'{personality_label(personality)}</span>'
                        )
                        if is_public:
                            badges += ' <span class="badge-public">🌍 Public</span>'
                        st.markdown(badges, unsafe_allow_html=True)
                    with row_col2:
                        if st.button("🗑️", key=f"delete_{chat_id}", use_container_width=True):
                            chats.delete_chat(chat_id)
                            if st.session_state.current_chat_id == chat_id:
                                st.session_state.current_chat_id = None
                            st.rerun()

    # ============================================
    # MAIN AREA — ANALYTICS DASHBOARD
    # ============================================
    if st.session_state.main_view == "analytics":
        data = chats.get_analytics(st.session_state.user_id)

        st.markdown('<p class="section-heading">📊 Your Chatbot Analytics</p>', unsafe_allow_html=True)

        m1, m2, m3 = st.columns(3)
        with m1:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-icon">💬</div>
                    <div class="metric-label">Total Chats</div>
                    <div class="metric-value">{data['total_chats']}</div>
                </div>
            """, unsafe_allow_html=True)
        with m2:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-icon">📨</div>
                    <div class="metric-label">Total Messages</div>
                    <div class="metric-value">{data['total_messages']}</div>
                </div>
            """, unsafe_allow_html=True)
        with m3:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-icon">📝</div>
                    <div class="metric-label">Avg AI Response</div>
                    <div class="metric-value">{data['avg_response_length']:.0f}<span style="font-size:1rem;color:#9CA3AF;"> words</span></div>
                </div>
            """, unsafe_allow_html=True)

        st.write("")

        # ---- NEW for Day 9: community stats row ----
        m4, m5, m6 = st.columns(3)
        with m4:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-icon">🌍</div>
                    <div class="metric-label">Public Chats</div>
                    <div class="metric-value">{data['public_chats']}</div>
                </div>
            """, unsafe_allow_html=True)
        with m5:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-icon">❤️</div>
                    <div class="metric-label">Likes Received</div>
                    <div class="metric-value">{data['likes_received']}</div>
                </div>
            """, unsafe_allow_html=True)
        with m6:
            st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-icon">💬</div>
                    <div class="metric-label">Comments Received</div>
                    <div class="metric-value">{data['comments_received']}</div>
                </div>
            """, unsafe_allow_html=True)

        st.write("")
        st.write("---")

        col_a, col_b = st.columns(2)

        with col_a:
            st.markdown("#### 🎭 Personality Usage")
            if data["personality_counts"]:
                df = pd.DataFrame(data["personality_counts"], columns=["Personality", "Chats"])
                df["Personality"] = df["Personality"].str.replace("_", " ").str.title()
                most_used = df.loc[df["Chats"].idxmax(), "Personality"]
                df = df.set_index("Personality")
                st.bar_chart(df, color="#6C63FF")
                st.success(f"🏆 Most used personality: **{most_used}**")
            else:
                st.markdown('<div class="analytics-empty">No data yet — start chatting! 🎭</div>', unsafe_allow_html=True)

        with col_b:
            st.markdown("#### 📈 Activity Over Time")
            if data["daily_counts"]:
                df2 = pd.DataFrame(data["daily_counts"], columns=["Date", "Messages"])
                df2 = df2.set_index("Date")
                st.line_chart(df2, color="#00E0FF")
            else:
                st.markdown('<div class="analytics-empty">No activity yet. 📈</div>', unsafe_allow_html=True)

    # ============================================
    # MAIN AREA — EXPLORE (NEW: public community feed)
    # ============================================
    elif st.session_state.main_view == "explore":

        if st.session_state.explore_view_chat_id:
            # ---- single public chat viewer ----
            if st.button("← Back to Explore"):
                st.session_state.explore_view_chat_id = None
                st.query_params.pop("share", None)
                st.rerun()

            chat_id = st.session_state.explore_view_chat_id
            conn_check = chats.get_chat_owner(chat_id)
            if conn_check is None:
                st.warning("This chat no longer exists.")
                st.session_state.explore_view_chat_id = None
            else:
                user_chats_lookup = chats.get_user_chats(st.session_state.user_id)
                title, personality = None, "mentor"
                # pull title/personality regardless of owner via a light query
                is_public, share_token = social.get_chat_public_info(chat_id)
                # get title/personality from chats table directly
                from database import get_connection
                _conn = get_connection()
                _row = _conn.execute("SELECT title, personality FROM chats WHERE id = ?", (chat_id,)).fetchone()
                _conn.close()
                if _row:
                    title, personality = _row

                p_info = personality_info(personality)
                st.markdown(
                    f'<p class="section-heading">{p_info["emoji"]} {title or "Untitled"}</p>',
                    unsafe_allow_html=True,
                )
                render_public_chat_viewer(chat_id, key_prefix="viewer")

        else:
            # ---- feed grid ----
            st.markdown('<p class="section-heading">🌍 Explore the Community</p>', unsafe_allow_html=True)

            top_col1, top_col2 = st.columns([3, 1])
            with top_col1:
                feed_search = st.text_input("🔍 Search public chats or authors",
                                             placeholder="e.g. python, mentor, murthu...",
                                             label_visibility="collapsed")
            with top_col2:
                sort_choice = st.selectbox("Sort by", ["🔥 Popular", "🆕 Recent"], label_visibility="collapsed")
                st.session_state.explore_sort = "popular" if "Popular" in sort_choice else "recent"

            feed = social.get_public_feed(sort_by=st.session_state.explore_sort,
                                           search_query=feed_search or None)

            if not feed:
                st.markdown(
                    '<div class="empty-feed">🌱 No public chats yet.<br>'
                    'Publish one of your chats to be the first on the feed!</div>',
                    unsafe_allow_html=True,
                )
            else:
                cols = st.columns(3)
                for idx, (chat_id, title, personality, created_at, owner, like_count, comment_count) in enumerate(feed):
                    p_info = personality_info(personality)
                    with cols[idx % 3]:
                        st.markdown(f"""
                            <div class="community-card">
                                <div class="community-title">{p_info['emoji']} {title or 'Untitled'}</div>
                                <div class="community-author">👤 by {owner}</div>
                                <span class="badge" style="background:{p_info['color']}">{personality_label(personality)}</span>
                                <div class="community-stats">
                                    <span>❤️ {like_count}</span>
                                    <span>💬 {comment_count}</span>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        view_col, author_col = st.columns([2, 1])
                        with view_col:
                            if st.button("👀 View", key=f"feedview_{chat_id}", use_container_width=True):
                                st.session_state.explore_view_chat_id = chat_id
                                st.rerun()
                        with author_col:
                            if st.button("👤", key=f"feedauthor_{chat_id}", use_container_width=True,
                                          help=f"View {owner}'s profile"):
                                st.session_state.profile_username = owner
                                st.session_state.main_view = "profile"
                                st.rerun()

    # ============================================
    # MAIN AREA — NOTIFICATIONS (NEW for Day 10)
    # ============================================
    elif st.session_state.main_view == "notifications":
        st.markdown('<p class="section-heading">🔔 Your Notifications</p>', unsafe_allow_html=True)

        notif_rows = notify.get_notifications(st.session_state.user_id)

        if not notif_rows:
            st.markdown(
                '<div class="empty-feed">🔕 No notifications yet.<br>'
                'Publish a chat to Explore and you\'ll hear about it when people like or comment!</div>',
                unsafe_allow_html=True,
            )
        else:
            if st.button("✅ Mark all as read"):
                notify.mark_all_read(st.session_state.user_id)
                st.rerun()

            for n_id, n_type, message, is_read, created_at, n_chat_id, from_user in notif_rows:
                css_class = "notif-read" if is_read else "notif-unread"
                icon = "❤️" if n_type == "like" else "💬"
                st.markdown(
                    f'<div class="notif-item {css_class}">{icon} {message}'
                    f'<span class="notif-time">{str(created_at)[:16]}</span></div>',
                    unsafe_allow_html=True,
                )
                jump_col, read_col = st.columns([1, 4])
                with jump_col:
                    if st.button("Open chat →", key=f"notif_open_{n_id}"):
                        if not is_read:
                            notify.mark_read(n_id)
                        st.session_state.explore_view_chat_id = n_chat_id
                        st.session_state.main_view = "explore"
                        st.rerun()

    # ============================================
    # MAIN AREA — PUBLIC PROFILE (NEW for Day 10)
    # ============================================
    elif st.session_state.main_view == "profile":
        profile_username = st.session_state.profile_username

        if not profile_username:
            st.info("No profile selected. Go to 🌍 Explore and click a 👤 icon.")
        else:
            back_col, share_col = st.columns([1, 1])
            with back_col:
                if st.button("← Back to Explore"):
                    st.session_state.main_view = "explore"
                    st.rerun()
            with share_col:
                with st.popover("🔗 Share this profile", use_container_width=True):
                    st.caption("Send this link — every click gets counted as a profile view:")
                    st.code(f"?profile={profile_username}", language=None)
                    st.caption("On the deployed app, prefix this with your app's URL.")

            # ---- NEW: profile views + traffic source, visible only to the owner ----
            if profile_username == st.session_state.username:
                total_views = profile_stats.get_total_views(profile_username)
                by_source = profile_stats.get_views_by_source(profile_username)
                with st.container(border=True):
                    st.markdown(f"##### 👁️ Profile Views — **{total_views:,}** total")
                    if by_source:
                        for source, count in by_source:
                            st.markdown(f"- **{source}**: {count:,} click(s)")
                    else:
                        st.caption("No views yet — share your profile link above! 🚀")

                # ---- Day 17: email notification preferences ----
                with st.container(border=True):
                    st.markdown("##### ✉️ Email Notifications")
                    if not email_service.is_configured():
                        st.caption(
                            "⚠️ Email sending isn't set up on this deployment yet "
                            "(SMTP_HOST/SMTP_USER/SMTP_PASSWORD missing from .env). "
                            "In-app 🔔 alerts still work as normal."
                        )
                    else:
                        current_email, current_enabled = auth.get_email_settings(st.session_state.user_id)
                        with st.form("email_settings_form"):
                            email_input = st.text_input(
                                "Email address",
                                value=current_email or "",
                                placeholder="you@example.com",
                            )
                            enabled_input = st.toggle(
                                "Email me when someone likes or comments on my chats",
                                value=current_enabled,
                            )
                            saved = st.form_submit_button("Save", type="primary")
                            if saved:
                                if enabled_input and (not email_input.strip() or "@" not in email_input):
                                    st.error("❌ Enter a valid email address to turn notifications on.")
                                else:
                                    auth.update_email_settings(
                                        st.session_state.user_id, email_input.strip() or None, enabled_input
                                    )
                                    st.success("✅ Saved!")
                                    st.rerun()

            st.markdown(
                f'<div class="profile-header"><span class="profile-avatar">🧑‍💻</span>'
                f'<p class="section-heading" style="margin:0;">{profile_username}\'s Public Chats</p></div>',
                unsafe_allow_html=True,
            )

            profile_chats = social.get_public_chats_by_user(profile_username)

            if not profile_chats:
                st.markdown(
                    '<div class="empty-feed">This user hasn\'t published anything yet. 🌱</div>',
                    unsafe_allow_html=True,
                )
            else:
                total_likes = sum(row[4] for row in profile_chats)
                st.caption(f"🌍 {len(profile_chats)} public chat(s)  ·  ❤️ {total_likes} total likes")
                cols = st.columns(3)
                for idx, (chat_id, title, personality, created_at, like_count, comment_count) in enumerate(profile_chats):
                    p_info = personality_info(personality)
                    with cols[idx % 3]:
                        st.markdown(f"""
                            <div class="community-card">
                                <div class="community-title">{p_info['emoji']} {title or 'Untitled'}</div>
                                <span class="badge" style="background:{p_info['color']}">{personality_label(personality)}</span>
                                <div class="community-stats">
                                    <span>❤️ {like_count}</span>
                                    <span>💬 {comment_count}</span>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                        if st.button("👀 View", key=f"profileview_{chat_id}", use_container_width=True):
                            st.session_state.explore_view_chat_id = chat_id
                            st.session_state.main_view = "explore"
                            st.rerun()

    # ============================================
    # MAIN AREA — PRICING (Day 20)
    # ============================================
    elif st.session_state.main_view == "pricing":
        st.markdown('<p class="section-heading">💎 Plans & Pricing</p>', unsafe_allow_html=True)

        # ---- Day 20 theme refresh: milestone banner for reaching Day 20 ----
        st.markdown(
            '<div class="milestone-banner">'
            '<span class="milestone-tag">DAY 20 MILESTONE</span>'
            'Payment system is live — plan requests now flow to an admin for approval.'
            '</div>',
            unsafe_allow_html=True,
        )

        # ---- Day 22: Razorpay checkout.js redirects back here with
        # ?razorpay=success&payment_id=...&order_id=...&signature=... —
        # catch that BEFORE rendering the plan cards below, verify the
        # signature server-side, and only then upgrade the plan. Never
        # trust the redirect params on their own.
        rzp_status = st.query_params.get("razorpay")
        if rzp_status == "success":
            rzp_payment_id = st.query_params.get("payment_id")
            rzp_order_id = st.query_params.get("order_id")
            rzp_signature = st.query_params.get("signature")
            ok, msg, _ = razorpay_service.verify_and_finalize(
                st.session_state.user_id, "pro", rzp_order_id, rzp_payment_id, rzp_signature
            )
            st.query_params.clear()
            if ok:
                st.success(f"✅ {msg}")
            else:
                st.error(f"⚠️ {msg}")

        current_plan = auth.get_user_plan(st.session_state.user_id)
        pending_plan = pricing.get_user_pending_request(st.session_state.user_id)

        plan_badge_class = {
            "free": "plan-badge-free",
            "pro": "plan-badge-pro",
            "enterprise": "plan-badge-enterprise",
        }
        st.markdown(
            f'You are currently on '
            f'<span class="plan-badge {plan_badge_class.get(current_plan, "plan-badge-free")}">'
            f'{pricing.PLANS.get(current_plan, pricing.PLANS["free"])["label"]}</span>',
            unsafe_allow_html=True,
        )

        if pending_plan:
            st.info(f"⏳ Your request to upgrade to **{pricing.PLANS[pending_plan]['label']}** is pending admin approval.")

        stripe_live = stripe_service.is_configured()
        razorpay_live = razorpay_service.is_configured()
        if stripe_live or razorpay_live:
            gateways = " / ".join(
                filter(None, ["Stripe" if stripe_live else None, "Razorpay" if razorpay_live else None])
            )
            st.caption(
                f"💳 Real payments are live for the Pro plan via {gateways} Checkout. Free and "
                "Enterprise still use the admin-approval flow below."
            )
        else:
            st.caption(
                "No live payment gateway is connected yet — requesting a plan below sends it to an "
                "admin for approval instead of charging a card. Real checkout can be wired in later "
                "without changing this page."
            )
        st.write("")

        checkout_status = st.query_params.get("checkout")
        if checkout_status == "success":
            st.success("✅ Payment received! Your plan will reflect Pro within a few seconds.")
        elif checkout_status == "cancelled":
            st.info("Checkout cancelled — no charge was made.")

        plan_cols = st.columns(3)
        for col, (plan_key, plan) in zip(plan_cols, pricing.PLANS.items()):
            with col:
                is_current = plan_key == current_plan
                with st.container(border=True):
                    st.markdown(
                        f"#### {plan['label']} "
                        f'<span class="plan-badge {plan_badge_class.get(plan_key, "plan-badge-free")}">'
                        f'{plan_key.upper()}</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"### {plan['price']}")
                    st.caption(plan['tagline'])
                    st.write("")
                    for feat in plan['features']:
                        st.markdown(f"✅ {feat}")
                    st.write("")
                    if is_current:
                        st.success("✓ Current plan")
                    elif (stripe_live or razorpay_live) and plan_key == "pro":
                        # Day 21: real Stripe Checkout — no admin approval needed,
                        # the webhook receiver upgrades the plan the moment payment succeeds.
                        if stripe_live:
                            if st.button("💳 Pay with Stripe", key=f"pay_{plan_key}", use_container_width=True, type="primary"):
                                checkout_url = stripe_service.create_checkout_session(st.session_state.user_id, plan_key)
                                if checkout_url:
                                    st.link_button("➡️ Continue to Stripe Checkout", checkout_url, use_container_width=True)
                                else:
                                    st.error("Couldn't start checkout — Stripe isn't fully configured yet.")
                        # Day 22: Razorpay Checkout — the INR-native alternative, no
                        # separate webhook service needed. checkout.js opens in-page and
                        # redirects back here on success; the signature gets verified
                        # server-side above, before we trust it (razorpay=success handler).
                        if razorpay_live:
                            if st.button("🇮🇳 Pay with Razorpay", key=f"rzp_{plan_key}", use_container_width=True):
                                order = razorpay_service.create_order(st.session_state.user_id, plan_key)
                                if order:
                                    app_url = razorpay_service.get_razorpay_keys()["app_url"].rstrip("/")
                                    widget_html = f"""
                                    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
                                    <script>
                                    var options = {{
                                        key: "{order['key_id']}",
                                        amount: "{order['amount']}",
                                        currency: "{order['currency']}",
                                        name: "Murthu AI Chatbot",
                                        description: "Pro plan — monthly subscription",
                                        order_id: "{order['order_id']}",
                                        handler: function (response) {{
                                            var url = "{app_url}/?razorpay=success"
                                                + "&payment_id=" + response.razorpay_payment_id
                                                + "&order_id=" + response.razorpay_order_id
                                                + "&signature=" + response.razorpay_signature;
                                            window.top.location.href = url;
                                        }},
                                        modal: {{
                                            ondismiss: function () {{
                                                window.top.location.href = "{app_url}/?checkout=cancelled";
                                            }}
                                        }}
                                    }};
                                    var rzp = new Razorpay(options);
                                    rzp.open();
                                    </script>
                                    """
                                    st.components.v1.html(widget_html, height=10)
                                else:
                                    st.error("Couldn't start checkout — Razorpay isn't fully configured yet.")
                    elif pending_plan == plan_key:
                        st.warning("⏳ Requested — awaiting approval")
                    else:
                        if st.button(f"Request {plan['label']}", key=f"req_{plan_key}", use_container_width=True):
                            ok, msg = pricing.create_upgrade_request(st.session_state.user_id, plan_key)
                            if ok:
                                st.success(f"✅ {msg}")
                            else:
                                st.warning(f"⚠️ {msg}")
                            st.rerun()

        # ---- Day 22: Invoice history + PDF download for every real
        # payment on record (Stripe or Razorpay). Manual admin-approval
        # upgrades never appear here — there's no charge to invoice for
        # those, which is the whole point of the Day 20 distinction.
        my_payments = invoice_service.get_user_payments(st.session_state.user_id)
        if my_payments:
            st.write("")
            st.markdown("#### 🧾 Billing history")
            for pay_id, gateway, plan_name, amount, currency, status, inv_num, created_at in my_payments:
                inv_col1, inv_col2, inv_col3 = st.columns([3, 2, 1])
                inv_col1.markdown(f"**{inv_num}** · {plan_name.title()} plan")
                inv_col2.caption(f"{gateway.title()} · {str(created_at)[:10]}")
                with inv_col3:
                    payment_row = invoice_service.get_payment(pay_id, user_id=st.session_state.user_id)
                    pdf_bytes = invoice_service.generate_invoice_pdf(payment_row)
                    st.download_button("⬇️ PDF", data=pdf_bytes, file_name=f"{inv_num}.pdf",
                                        mime="application/pdf", key=f"inv_{pay_id}", use_container_width=True)

    # ============================================
    # MAIN AREA — ADMIN PANEL (Day 18, admins only)
    # ============================================
    elif st.session_state.main_view == "admin" and is_admin_user:
        st.markdown('<p class="section-heading">🛡️ Admin Dashboard</p>', unsafe_allow_html=True)

        totals = admin_service.get_platform_totals()
        t1, t2, t3, t4 = st.columns(4)
        t1.metric("Total Users", f"{totals['total_users']:,}")
        t2.metric("Total Chats", f"{totals['total_chats']:,}")
        t3.metric("Total Messages", f"{totals['total_messages']:,}")
        t4.metric("Pro/Enterprise", f"{totals['by_plan'].get('pro', 0) + totals['by_plan'].get('enterprise', 0):,}")

        st.write("")
        search_q = st.text_input("🔍 Search by username or email", key="admin_search")
        st.write("")

        rows = admin_service.list_users_with_stats()
        columns = ["id", "username", "email", "plan", "is_admin", "oauth_provider",
                   "created_at", "total_chats", "total_messages", "public_chats"]
        df = pd.DataFrame(rows, columns=columns)

        if search_q.strip():
            q = search_q.strip().lower()
            df = df[
                df["username"].str.lower().str.contains(q, na=False)
                | df["email"].fillna("").str.lower().str.contains(q, na=False)
            ]

        df["is_admin"] = df["is_admin"].astype(bool)
        df_display = df.rename(columns={
            "username": "Username", "email": "Email", "plan": "Plan",
            "is_admin": "Admin", "oauth_provider": "Login via",
            "created_at": "Joined", "total_chats": "Chats",
            "total_messages": "Messages", "public_chats": "Public",
        })

        edited = st.data_editor(
            df_display,
            column_config={
                "id": None,  # hide raw id column, still available in df
                "Plan": st.column_config.SelectboxColumn(options=admin_service.PLAN_OPTIONS, required=True),
                "Admin": st.column_config.CheckboxColumn(),
                "Login via": st.column_config.TextColumn(disabled=True),
                "Chats": st.column_config.NumberColumn(disabled=True),
                "Messages": st.column_config.NumberColumn(disabled=True),
                "Public": st.column_config.NumberColumn(disabled=True),
                "Joined": st.column_config.TextColumn(disabled=True),
                "Username": st.column_config.TextColumn(disabled=True),
                "Email": st.column_config.TextColumn(disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key="admin_user_editor",
        )

        if st.button("💾 Save changes", type="primary"):
            changes = 0
            errors = []
            for i in range(len(df)):
                user_id = int(df.iloc[i]["id"])
                orig_plan = df.iloc[i]["plan"]
                orig_admin = bool(df.iloc[i]["is_admin"])
                new_plan = edited.iloc[i]["Plan"]
                new_admin = bool(edited.iloc[i]["Admin"])

                if new_plan != orig_plan:
                    admin_service.set_user_plan(user_id, new_plan)
                    changes += 1
                if new_admin != orig_admin:
                    ok, msg = admin_service.set_user_admin(user_id, new_admin, st.session_state.user_id)
                    if not ok:
                        errors.append(f"{df.iloc[i]['username']}: {msg}")
                    else:
                        changes += 1

            if changes:
                st.success(f"✅ Saved {changes} change(s).")
            for e in errors:
                st.warning(f"⚠️ {e}")
            if changes or errors:
                st.rerun()

        st.write("---")
        with st.expander("🔑 Reset a user's password"):
            reset_username = st.selectbox("User", df["username"].tolist(), key="admin_reset_user")
            new_pw = st.text_input("New password", type="password", key="admin_reset_pw")
            if st.button("Reset password", key="admin_reset_btn"):
                if len(new_pw) < 6:
                    st.error("❌ Password must be at least 6 characters!")
                else:
                    target_id = int(df[df["username"] == reset_username].iloc[0]["id"])
                    admin_service.reset_user_password(target_id, new_pw)
                    st.success(f"✅ Password reset for {reset_username}.")

        # ---- Day 20: pending plan-upgrade requests ----
        pending_requests = pricing.get_pending_requests()
        st.write("---")
        st.markdown(f"##### 💎 Pending Upgrade Requests ({len(pending_requests)})")
        if not pending_requests:
            st.caption("No pending requests.")
        else:
            for req_id, username, requested_plan, created_at, target_user_id in pending_requests:
                r_col1, r_col2, r_col3 = st.columns([3, 1, 1])
                with r_col1:
                    st.markdown(f"**{username}** → {pricing.PLANS[requested_plan]['label']} · {created_at}")
                with r_col2:
                    if st.button("✅ Approve", key=f"approve_{req_id}", use_container_width=True):
                        admin_service.set_user_plan(target_user_id, requested_plan)
                        pricing.resolve_request(req_id, approve=True)
                        st.success(f"✅ {username} upgraded to {requested_plan}.")
                        st.rerun()
                with r_col3:
                    if st.button("❌ Reject", key=f"reject_{req_id}", use_container_width=True):
                        pricing.resolve_request(req_id, approve=False)
                        st.rerun()

    # ============================================
    # MAIN AREA — CHAT VIEW
    # ============================================
    else:
        if st.session_state.current_chat_id:
            from database import get_connection
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT title, personality FROM chats WHERE id = ?',
                          (st.session_state.current_chat_id,))
            chat_info = cursor.fetchone()
            conn.close()

            if chat_info is None:
                st.session_state.current_chat_id = None
                st.rerun()

            title, personality = chat_info
            chat_id = st.session_state.current_chat_id
            p_info = personality_info(personality)
            system_prompt = p_info["prompt"]
            history = chats.get_chat_history(chat_id)
            is_public, share_token = social.get_chat_public_info(chat_id)

            # ---- header row with publish + export buttons ----
            head_col1, head_col2, head_col3, head_col4 = st.columns([2.4, 1, 1, 1])
            with head_col1:
                badge = ' <span class="badge-public">🌍 Public</span>' if is_public else ""
                st.markdown(
                    f'#### {p_info["emoji"]} {title or "Untitled"} '
                    f'<span class="badge" style="background:{p_info["color"]}">'
                    f'{personality_label(personality)}</span>{badge}',
                    unsafe_allow_html=True
                )
            with head_col2:
                publish_label = "🌍 Unpublish" if is_public else "📢 Publish"
                if st.button(publish_label, use_container_width=True, key=f"publish_{chat_id}"):
                    social.set_chat_public(chat_id, not is_public)
                    st.rerun()
            with head_col3:
                json_data = export_chat_json(title, personality, history)
                st.download_button("⬇️ JSON", data=json_data,
                                    file_name=f"{title or 'chat'}.json",
                                    mime="application/json", use_container_width=True,
                                    disabled=len(history) == 0)
            with head_col4:
                if history:
                    try:
                        pdf_bytes = export_chat_pdf(title, personality, history)
                        st.download_button("⬇️ PDF", data=pdf_bytes,
                                            file_name=f"{title or 'chat'}.pdf",
                                            mime="application/pdf", use_container_width=True)
                    except Exception as e:
                        st.button("⬇️ PDF", use_container_width=True, disabled=True)
                        st.caption(f"⚠️ PDF export failed: {e}")
                else:
                    st.button("⬇️ PDF", use_container_width=True, disabled=True)

            # ---- NEW for Day 9: like/share/comments strip when a chat is public ----
            if is_public:
                st.write("")
                with st.expander(f"🌍 Community activity — ❤️ {social.get_like_count(chat_id)} · 💬 {social.get_comment_count(chat_id)}", expanded=False):
                    render_like_and_share(chat_id, share_token, key_prefix="own")
                    st.write("")
                    render_comments(chat_id, key_prefix="own")

            # ---- Day 19: file uploads attached to this chat ----
            attachments = upload_service.get_attachments_for_chat(chat_id)
            with st.expander(f"📎 Attachments ({len(attachments)})", expanded=False):
                new_file = st.file_uploader(
                    "Attach a file",
                    type=upload_service.ALLOWED_EXTENSIONS,
                    key=f"uploader_{chat_id}",
                    help=f"Max {upload_service.human_size(upload_service.MAX_FILE_SIZE_BYTES)} per file. "
                         f"Images, PDFs, and text files.",
                )
                if new_file is not None:
                    file_bytes = new_file.getvalue()
                    ok, msg = upload_service.save_attachment(
                        chat_id, st.session_state.user_id, new_file.name, new_file.type or "application/octet-stream", file_bytes
                    )
                    if ok:
                        st.success(f"✅ {new_file.name} uploaded!")
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

                if attachments:
                    st.write("")
                    for att_id, filename, mime_type, size_bytes, created_at in attachments:
                        a_col1, a_col2, a_col3 = st.columns([3, 1, 1])
                        with a_col1:
                            icon = "🖼️" if upload_service.is_image(filename) else "📄"
                            st.markdown(f"{icon} **{filename}** · {upload_service.human_size(size_bytes)}")
                        with a_col2:
                            file_data, f_mime, f_name = upload_service.get_attachment_data(att_id)
                            st.download_button("⬇️", data=file_data, file_name=f_name, mime=f_mime,
                                                key=f"dl_{att_id}", use_container_width=True)
                        with a_col3:
                            if st.button("🗑️", key=f"del_att_{att_id}", use_container_width=True):
                                upload_service.delete_attachment(att_id, st.session_state.user_id)
                                st.rerun()
                        if upload_service.is_image(filename):
                            img_data, _, _ = upload_service.get_attachment_data(att_id)
                            st.image(img_data, width=220)
                else:
                    st.caption("No files attached yet.")

            st.write("---")

            for role, content in history:
                if role == "user":
                    st.chat_message("user", avatar="🧑").write(content)
                else:
                    st.chat_message("assistant", avatar=p_info["emoji"]).write(content)

            user_input = st.chat_input("Type your message...")

            if user_input:
                chats.save_message(chat_id, "user", user_input)
                st.chat_message("user", avatar="🧑").write(user_input)

                with st.spinner(f"{p_info['emoji']} Thinking..."):
                    messages = [{"role": "system", "content": system_prompt}]
                    for role, content in history:
                        messages.append({"role": role, "content": content})
                    messages.append({"role": "user", "content": user_input})

                    try:
                        response = client.chat.completions.create(
                            model="llama-3.3-70b-versatile",
                            messages=messages
                        )
                        ai_reply = response.choices[0].message.content
                    except Exception as e:
                        ai_reply = f"⚠️ Error getting AI response: {str(e)}"

                    chats.save_message(chat_id, "assistant", ai_reply)
                    st.chat_message("assistant", avatar=p_info["emoji"]).write(ai_reply)

                st.rerun()

        else:
            st.info("👈 Select a chat from the sidebar, create a new one, or check out 🌍 **Explore** to see what the community is building!")
