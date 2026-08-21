# ============================================
# smtp_debug.py — run this directly to see EXACTLY why email isn't sending.
# Usage:  python smtp_debug.py
# (Run it from inside your project folder, next to your .env file)
# ============================================

import os
from dotenv import load_dotenv

load_dotenv()

host = os.getenv("SMTP_HOST")
port = os.getenv("SMTP_PORT")
user = os.getenv("SMTP_USER")
password = os.getenv("SMTP_PASSWORD")

print("---- Checking .env values ----")
print("SMTP_HOST:", host)
print("SMTP_PORT:", port)
print("SMTP_USER:", user)
print("SMTP_PASSWORD:", f"{'*' * (len(password)-4)}{password[-4:]}" if password else None,
      f"(length={len(password) if password else 0})")

if not (host and port and user and password):
    print("\n❌ One or more SMTP_* variables are MISSING from .env — that's the problem.")
    print("   Make sure they're in the .env file in your PROJECT folder, not somewhere else.")
    raise SystemExit

print("\n---- Attempting real send ----")
import smtplib
import ssl
from email.mime.text import MIMEText

to_email = input("Send test email to (press Enter to send to yourself): ").strip() or user

try:
    msg = MIMEText("This is a test email from your chatbot project. If you see this, SMTP works! ✅")
    msg["Subject"] = "SMTP Test — Murthu AI Chatbot"
    msg["From"] = user
    msg["To"] = to_email

    context = ssl.create_default_context()
    with smtplib.SMTP(host, int(port)) as server:
        server.set_debuglevel(1)   # prints the full SMTP conversation
        server.starttls(context=context)
        server.login(user, password)
        server.sendmail(user, to_email, msg.as_string())

    print(f"\n✅ SUCCESS — check the inbox (and spam folder) of {to_email}")
except Exception as e:
    print(f"\n❌ FAILED: {type(e).__name__}: {e}")
