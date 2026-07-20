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
    /* ---------- NEW for Day 16: nav buttons feel snappier ---------- */
    .stButton > button:active { transform: translateY(0px) scale(0.98); }

    /* ---------- NEW for Day 17: professional split-screen auth theme ---------- */
    /* ---------- Day 18 update: orange-forward gradient + floating "robotics" particles ---------- */
    .auth-hero {
        position: relative;
        padding: 2.2rem 2rem;
        border-radius: 20px;
        background:
            radial-gradient(circle at 15% 15%, rgba(255,138,50,0.22), transparent 55%),
            radial-gradient(circle at 85% 20%, rgba(255,184,77,0.20), transparent 50%),
            radial-gradient(circle at 60% 90%, rgba(255,90,95,0.14), transparent 55%),
            linear-gradient(160deg, rgba(255,255,255,0.03), rgba(255,255,255,0.00));
        border: 1px solid rgba(255,159,67,0.18);
        overflow: hidden;
    }
    .auth-floaters {
        position: absolute;
        inset: 0;
        pointer-events: none;
        z-index: 0;
    }
    .auth-floaters .floater {
        position: absolute;
        font-size: 1.6rem;
        opacity: 0.28;
        filter: drop-shadow(0 0 10px rgba(255,159,67,0.55));
        animation: floaty 7s ease-in-out infinite;
    }
    .floater.f1 { top: 8%;  left: 6%;  font-size: 2.1rem; animation-delay: 0s;    }
    .floater.f2 { top: 65%; left: 10%; font-size: 1.3rem; animation-delay: 1.1s; }
    .floater.f3 { top: 20%; left: 88%; font-size: 1.7rem; animation-delay: 2.3s; }
    .floater.f4 { top: 78%; left: 82%; font-size: 2.4rem; animation-delay: 0.6s; }
    .floater.f5 { top: 45%; left: 50%; font-size: 1.1rem; animation-delay: 1.8s; }
    .floater.f6 { top: 5%;  left: 45%; font-size: 1.2rem; animation-delay: 3s;   }
    @keyframes floaty {
        0%   { transform: translateY(0px) rotate(0deg); }
        50%  { transform: translateY(-16px) rotate(8deg); }
        100% { transform: translateY(0px) rotate(0deg); }
    }
    .auth-hero-badge, .auth-hero-title, .auth-hero-sub, .auth-feature-row {
        position: relative;
        z-index: 1;
    }
    .auth-hero-badge {
        display: inline-block;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.3px;
        color: #FFB84D;
        background: rgba(255,184,77,0.12);
        border: 1px solid rgba(255,184,77,0.3);
        padding: 4px 12px;
        border-radius: 999px;
        margin-bottom: 1rem;
    }
    .auth-hero-title {
        font-size: 1.9rem;
        font-weight: 800;
        line-height: 1.25;
        margin: 0 0 0.7rem 0;
        letter-spacing: -0.5px;
    }
    .auth-hero-sub {
        color: #9CA3AF;
        font-size: 1rem;
        line-height: 1.55;
        margin-bottom: 1.6rem;
    }
    .auth-feature-row {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 0.9rem;
    }
    .auth-feature {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        font-size: 0.88rem;
        padding: 0.7rem;
        border-radius: 12px;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.05);
    }
    .auth-feature-icon { font-size: 1.3rem; line-height: 1; }
    .auth-feature-sub { color: #9CA3AF; font-size: 0.78rem; }
    .auth-trust-row {
        display: flex;
        gap: 1.4rem;
        flex-wrap: wrap;
        margin-top: 1rem;
        padding: 0.9rem 0.2rem 0.2rem 0.2rem;
        font-size: 0.85rem;
        color: #D1D5DB;
    }

    /* Login/Register card itself — give the bordered container real presence */
    div[data-testid="stForm"] {
        border-radius: 16px !important;
        border: 1px solid rgba(255,255,255,0.08) !important;
        background: rgba(255,255,255,0.02);
        padding-top: 0.4rem;
    }
    div[data-testid="stTextInput"] input {
        border-radius: 10px !important;
    }
    div[data-testid="stTextInput"] input:focus {
        box-shadow: 0 0 0 2px rgba(255,90,95,0.4) !important;
        border-color: #FF5A5F !important;
    }

    @media (max-width: 900px) {
        .auth-feature-row { grid-template-columns: 1fr; }
    }

    /* ---------- NEW for Day 18: premium depth + admin panel polish ---------- */
    .stButton > button {
        box-shadow: 0 1px 2px rgba(0,0,0,0.25);
        transition: transform 0.12s ease, box-shadow 0.12s ease;
    }
    .stButton > button:hover {
        box-shadow: 0 4px 14px rgba(255,90,95,0.22);
        transform: translateY(-1px);
    }
    div[data-testid="stMetric"] {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px;
        padding: 0.9rem 1rem;
    }
    div[data-testid="stMetricValue"] {
        font-weight: 800;
        background: linear-gradient(90deg, #FF5A5F, #FFB84D);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    div[data-testid="stDataFrame"], div[data-testid="stDataEditor"] {
        border-radius: 14px;
        overflow: hidden;
        border: 1px solid rgba(255,255,255,0.08);
    }
</style>
"""
