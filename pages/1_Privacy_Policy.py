# ============================================
# Privacy Policy — standalone page
# Lives at: <your-app-url>/Privacy_Policy
# No login required — must be publicly viewable for Razorpay verification.
# ============================================

import streamlit as st

st.set_page_config(
    page_title="Privacy Policy | Murthu AI Chatbot",
    page_icon="🔒",
    layout="centered"
)

st.markdown("""
<style>
.legal-wrap h1 { font-size: 2rem; margin-bottom: 0.2rem; }
.legal-wrap .updated { color: #888; font-size: 0.9rem; margin-bottom: 1.5rem; }
.legal-wrap h2 { font-size: 1.25rem; margin-top: 1.8rem; margin-bottom: 0.5rem; }
.legal-wrap p, .legal-wrap li { font-size: 0.98rem; line-height: 1.6; }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="legal-wrap">', unsafe_allow_html=True)

st.markdown("# 🔒 Privacy Policy")

st.markdown(
    '<p class="updated">Effective date: July 21, 2026 &nbsp;|&nbsp; '
    'Last updated: July 21, 2026</p>',
    unsafe_allow_html=True
)

st.markdown("""
**Murthu AI Chatbot** ("we", "our", "us") is a personal AI chatbot project
created to provide useful AI-powered tools and services for **students,
developers, learners, professionals, and the general public**.

This Privacy Policy explains what information we collect when you use our
website/app at **murthu-ai-chatbot.streamlit.app**, how we use it, and the
choices you have.

By creating an account or using the platform, you agree to the practices
described in this policy.
""")

st.markdown("## 1. Information We Collect")

st.markdown("""
**Account information**
- Username, email address, and a securely hashed password (if you sign up directly), or
- Your name, email, and profile picture (if you sign in with **Google OAuth** — we never see or store your Google password)

**Content you create**
- Chat messages and conversations you have with the AI, and any chats you choose to publish publicly
- Comments and likes on public chats
- Files you upload (capped at 3 MB per file)

**Usage & technical data**
- Login sessions, timestamps, and basic activity logs (e.g. chats created, likes, comments) used to power features like notifications and analytics
- Standard technical data such as browser type, needed to operate the service

**Payment information**
- If you upgrade to a paid plan, payments are processed by **Razorpay**.
- We do **not** collect or store your card, UPI, or bank details ourselves.
- Payment information is handled directly and securely by Razorpay under their own privacy and security standards.
""")

st.markdown("## 2. How We Use Your Information")

st.markdown("""
- To create and manage your account and authenticate your logins
- To operate core features such as chats, public profiles, notifications, comments, likes, and search
- To provide AI-powered assistance and useful tools for students, developers, learners, professionals, and other users
- To send you optional email notifications (only if you opt in)
- To process plan upgrades and payments via Razorpay
- To maintain the security, stability, and abuse-prevention of the platform
- To improve the product based on aggregate, non-identifying usage patterns
""")

st.markdown("## 3. AI Processing (Groq)")

st.markdown("""
Your chat messages are sent to **Groq**, our AI inference provider, solely
to generate AI responses in real time.

Messages are processed to return a reply and are not used by us to train
third-party models.
""")

st.markdown("## 4. Sharing of Information")

st.markdown("""
We do **not sell your personal information**. We only share data with:

- **Razorpay** — to process payments, when you choose to upgrade your plan
- **Groq** — to generate AI chat responses
- **Google** — only if you choose to sign in with Google OAuth
- Law enforcement or regulators, only if legally required to do so

Any chat you explicitly mark as **public** is visible to other users of the
platform, including its content, your username, and engagement
(likes/comments).
""")

st.markdown("## 5. Data Storage & Security")

st.markdown("""
- Passwords are never stored in plain text — they are securely hashed
- Data is stored in our managed database and access is restricted to the platform's core services
- We take reasonable technical and organizational measures to protect your data, though no online service can guarantee absolute security
""")

st.markdown("## 6. Data Retention")

st.markdown("""
We retain your account and chat data for as long as your account is active.

You may request deletion of your account and associated data at any time by
contacting us (see Section 9). We will action such requests within a
reasonable timeframe, subject to any legal record-keeping requirements,
including payment-related records where applicable.
""")

st.markdown("## 7. Your Rights & Choices")

st.markdown("""
- **Access & correction** — you can view and edit your profile information from within the app
- **Deletion** — you may request full account deletion at any time
- **Email notifications** — these are opt-in and can be turned off from your profile settings
- **Public chats** — you control which chats are made public, and can unpublish them
""")

st.markdown("## 8. Children's Privacy")

st.markdown("""
This platform is designed to be useful for students, developers, learners,
professionals, and the general public.

The platform is not directed specifically at children under 13, and we do
not knowingly collect personal information from children under 13.
""")

st.markdown("## 9. Contact Us")

st.markdown("""
If you have questions about this Privacy Policy, or wish to access, correct,
or delete your data, contact us at:

📧 **luckymurthu@gmail.com**

**Murthu AI Chatbot**
""")

st.markdown("## 10. Changes to This Policy")

st.markdown("""
We may update this Privacy Policy from time to time.

Material changes will be reflected by updating the **"Last updated"** date at
the top of this page. Continued use of the platform after changes constitutes
acceptance of the updated policy.
""")

st.markdown("---")

st.page_link(
    "chatbot.py",
    label="⬅ Back to Murthu AI Chatbot",
    icon="🤖"
)

st.markdown('</div>', unsafe_allow_html=True)
