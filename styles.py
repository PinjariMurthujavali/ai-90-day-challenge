# ============================================
# Day 9: styles.py
# All the injected CSS lives here so app.py stays readable.
# ============================================

APP_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* ---------- Header ---------- */
    .main-title {
        font-size: 2.8rem;
        font-weight: 800;
        background: linear-gradient(90deg, #FF5A5F, #FF8A65, #FFB84D);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0;
        letter-spacing: -0.5px;
    }
    .sub-title {
        color: #9CA3AF;
        font-size: 1.05rem;
        margin-top: 0.1rem;
        margin-bottom: 1.2rem;
    }

    /* ---------- Buttons ---------- */
    .stButton > button {
        border-radius: 12px;
        font-weight: 600;
        transition: all 0.2s ease;
        border: 1px solid rgba(255,255,255,0.06);
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(255, 90, 95, 0.35);
    }
    div[data-testid="stChatMessage"] {
        border-radius: 16px;
        border: 1px solid rgba(255,255,255,0.06);
    }
    .stDownloadButton > button {
        border-radius: 12px;
        font-weight: 600;
    }

    /* ---------- Badges ---------- */
    .badge {
        display: inline-block;
        padding: 3px 14px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 700;
        color: white;
        letter-spacing: 0.3px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.25);
    }
    .badge-public {
        display: inline-block;
        padding: 3px 12px;
        border-radius: 999px;
        font-size: 0.7rem;
        font-weight: 700;
        color: white;
        background: linear-gradient(90deg, #10B981, #34D399);
        letter-spacing: 0.3px;
    }

    /* ---------- Analytics metric cards ---------- */
    .metric-card {
        background: linear-gradient(155deg, rgba(255,90,95,0.14), rgba(255,90,95,0.02));
        border: 1px solid rgba(255,90,95,0.25);
        border-radius: 18px;
        padding: 1.1rem 1.3rem;
        text-align: left;
        transition: transform 0.15s ease;
    }
    .metric-card:hover { transform: translateY(-3px); }
    .metric-label {
        font-size: 0.82rem;
        color: #9CA3AF;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        margin-bottom: 0.3rem;
    }
    .metric-value {
        font-size: 2.1rem;
        font-weight: 800;
        color: #FFFFFF;
        line-height: 1;
    }
    .metric-icon { font-size: 1.6rem; margin-bottom: 0.4rem; }

    .section-heading {
        font-size: 1.3rem;
        font-weight: 700;
        margin: 1.4rem 0 0.6rem 0;
        background: linear-gradient(90deg, #FF5A5F, #FFB84D);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: inline-block;
    }

    .analytics-empty {
        border: 1px dashed rgba(255,255,255,0.15);
        border-radius: 14px;
        padding: 2rem;
        text-align: center;
        color: #9CA3AF;
    }

    hr { border-color: rgba(255,255,255,0.08) !important; }

    /* ---------- NEW for Day 9: Community feed cards ---------- */
    .community-card {
        background: linear-gradient(155deg, rgba(255,255,255,0.04), rgba(255,255,255,0.01));
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 18px;
        padding: 1.1rem 1.2rem 0.8rem 1.2rem;
        margin-bottom: 0.9rem;
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .community-card:hover {
        transform: translateY(-3px);
        border-color: rgba(255,90,95,0.4);
    }
    .community-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #F3F4F6;
        margin-bottom: 0.15rem;
    }
    .community-author {
        font-size: 0.82rem;
        color: #9CA3AF;
        margin-bottom: 0.5rem;
    }
    .community-stats {
        font-size: 0.85rem;
        color: #D1D5DB;
        font-weight: 600;
        display: flex;
        gap: 14px;
        margin-top: 0.3rem;
    }

    /* ---------- NEW for Day 9: comment bubbles ---------- */
    .comment-box {
        background: rgba(255,255,255,0.035);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px;
        padding: 0.6rem 0.9rem;
        margin-bottom: 0.5rem;
    }
    .comment-author {
        font-weight: 700;
        font-size: 0.85rem;
        color: #FF8A65;
    }
    .comment-time {
        font-size: 0.72rem;
        color: #6B7280;
        margin-left: 6px;
    }
    .comment-content {
        font-size: 0.92rem;
        color: #E5E7EB;
        margin-top: 2px;
    }

    .like-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-weight: 700;
    }

    /* ---------- NEW for Day 10: notifications ---------- */
    .notif-item {
        border-radius: 12px;
        padding: 0.55rem 0.8rem;
        margin-bottom: 0.4rem;
        font-size: 0.86rem;
    }
    .notif-unread {
        background: rgba(255,90,95,0.12);
        border: 1px solid rgba(255,90,95,0.3);
    }
    .notif-read {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.06);
        color: #9CA3AF;
    }
    .notif-time {
        font-size: 0.7rem;
        color: #6B7280;
        display: block;
        margin-top: 2px;
    }
    .bell-badge {
        background: #FF5A5F;
        color: white;
        border-radius: 999px;
        padding: 1px 7px;
        font-size: 0.7rem;
        font-weight: 800;
        margin-left: 4px;
    }
    .profile-header {
        display: flex;
        align-items: center;
        gap: 12px;
        margin-bottom: 0.5rem;
    }
    .profile-avatar {
        font-size: 2.2rem;
    }

    .empty-feed {
        border: 1px dashed rgba(255,255,255,0.15);
        border-radius: 16px;
        padding: 2.5rem;
        text-align: center;
        color: #9CA3AF;
    }

    /* ---------- NEW for Day 16: real-time live badge ---------- */
    .live-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        background: rgba(16,185,129,0.14);
        border: 1px solid rgba(16,185,129,0.4);
        color: #34D399;
        font-size: 0.75rem;
        font-weight: 700;
        padding: 2px 10px;
        border-radius: 999px;
        vertical-align: middle;
        animation: live-pulse 2s ease-in-out infinite;
    }
    @keyframes live-pulse {
        0%   { box-shadow: 0 0 0 0 rgba(16,185,129,0.45); }
        70%  { box-shadow: 0 0 0 7px rgba(16,185,129,0); }
        100% { box-shadow: 0 0 0 0 rgba(16,185,129,0); }
    }

    /* ---------- NEW for Day 16: nav buttons feel snappier ---------- */
    .stButton > button:active { transform: translateY(0px) scale(0.98); }
</style>
"""
