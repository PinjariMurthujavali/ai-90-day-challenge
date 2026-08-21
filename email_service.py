# ============================================
# Day 17: email_service.py  (NEW FILE)
# Real email sending via SMTP (stdlib smtplib — no extra package needed,
# so requirements.txt doesn't grow). Works with Gmail SMTP, Outlook,
# SendGrid's SMTP relay, or any standard SMTP provider.
#
# Like oauth.py's Google login, this is fully optional: if the SMTP
# .env vars aren't set, is_configured() returns False and every caller
# in the app just skips sending — nothing breaks, nothing shows an
# error to the user.
#
# .env vars (all optional):
#   SMTP_HOST        e.g. smtp.gmail.com
#   SMTP_PORT         e.g. 587
#   SMTP_USER         the mailbox that sends (e.g. you@gmail.com)
#   SMTP_PASSWORD     an app password (NOT your normal login password —
#                     Gmail requires a 16-char "App Password" with 2FA on)
#   FROM_NAME         display name, e.g. "Murthu AI Chatbot"  (optional,
#                     defaults to SMTP_USER)
# ============================================

import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _cfg():
    return {
        "host": os.getenv("SMTP_HOST"),
        "port": os.getenv("SMTP_PORT"),
        "user": os.getenv("SMTP_USER"),
        "password": os.getenv("SMTP_PASSWORD"),
        "from_name": os.getenv("FROM_NAME") or "Murthu AI Chatbot",
    }


def is_configured():
    c = _cfg()
    return bool(c["host"] and c["port"] and c["user"] and c["password"])


def _wrap_html(inner_html):
    """Shared email chrome — same gradient brand feel as the app's login
    page, so the email actually looks like it came from this product."""
    return f"""
    <div style="font-family: 'Segoe UI', Arial, sans-serif; background:#0F1117; padding:32px 16px;">
      <div style="max-width:480px; margin:0 auto; background:#171923; border-radius:16px;
                  overflow:hidden; border:1px solid rgba(255,255,255,0.08);">
        <div style="padding:28px 28px 20px 28px;
                    background:linear-gradient(90deg,#FF5A5F,#FF8A65,#FFB84D);">
          <span style="font-size:22px; font-weight:800; color:#111;">🤖 Murthu AI Chatbot</span>
        </div>
        <div style="padding:28px; color:#E5E7EB; font-size:15px; line-height:1.6;">
          {inner_html}
        </div>
        <div style="padding:16px 28px; color:#6B7280; font-size:12px; border-top:1px solid rgba(255,255,255,0.06);">
          You're receiving this because you have an account on Murthu AI Chatbot.
          You can turn email notifications off anytime from your Profile page.
        </div>
      </div>
    </div>
    """


def send_email(to_email, subject, html_body):
    """Returns (success: bool, error_message: str | None). Never raises —
    callers (notification_service, registration) treat email as best-effort
    and must not break the main flow if SMTP is down or misconfigured."""
    if not is_configured():
        return False, "SMTP not configured"
    if not to_email:
        return False, "No recipient email"

    c = _cfg()
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{c['from_name']} <{c['user']}>"
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP(c["host"], int(c["port"])) as server:
            server.starttls(context=context)
            server.login(c["user"], c["password"])
            server.sendmail(c["user"], to_email, msg.as_string())
        return True, None
    except Exception as e:
        return False, str(e)


def send_welcome_email(to_email, username):
    inner = f"""
        <p>Hey <strong>{username}</strong>, welcome aboard! 🎉</p>
        <p>Your account is ready. Jump in and start a chat with any of our AI personalities,
        publish your best conversations to the community, and watch the likes roll in.</p>
        <p style="margin-top:20px;">— The Murthu AI team</p>
    """
    return send_email(to_email, "Welcome to Murthu AI Chatbot 🤖", _wrap_html(inner))


def send_activity_email(to_email, username, message):
    inner = f"""
        <p>Hi <strong>{username}</strong>,</p>
        <p style="background:rgba(255,90,95,0.1); border-left:3px solid #FF5A5F;
                   padding:12px 16px; border-radius:6px;">
            {message}
        </p>
        <p style="margin-top:20px;">Log in to see the full conversation and reply.</p>
    """
    return send_email(to_email, "🔔 New activity on your chat", _wrap_html(inner))
