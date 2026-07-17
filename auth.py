# ============================================
# Day 10: auth.py
# Everything about who-is-this-user: register, login,
# password hashing, and persistent session tokens.
# ============================================

import hashlib
import secrets
import sqlite3

from database import get_connection


def hash_password(password):
    # NOTE: sha256 without salt is weak for production use.
    # Consider bcrypt / werkzeug.security.generate_password_hash instead.
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(username, password):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        password_hash = hash_password(password)
        cursor.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                       (username, password_hash))
        conn.commit()
        conn.close()
        return True, "Registration successful!"
    except Exception as e:
        # sqlite3 raises IntegrityError for UNIQUE violations; libsql/Turso
        # raises a different exception class with "UNIQUE constraint" (or
        # similar) in the message — check the text so both are caught.
        err_text = str(e).lower()
        if "unique" in err_text or "constraint" in err_text:
            return False, "USERNAME_EXISTS"
        return False, f"Error: {str(e)}"


def login_user(username, password):
    conn = get_connection()
    cursor = conn.cursor()
    password_hash = hash_password(password)
    cursor.execute('SELECT id, username FROM users WHERE username = ? AND password_hash = ?',
                   (username, password_hash))
    user = cursor.fetchone()
    conn.close()
    if user:
        return True, user[0]
    return False, None


def get_username(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "Unknown"


def get_avatar_url(user_id):
    """Google profile picture for OAuth users, None for username/password
    accounts (the UI falls back to a plain emoji avatar in that case)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT avatar_url FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None


def get_user_id_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


# ---- persistent session (token) functions ----

def create_session(user_id):
    token = secrets.token_hex(16)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO sessions (token, user_id) VALUES (?, ?)', (token, user_id))
    conn.commit()
    conn.close()
    return token


def get_user_by_token(token):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.username FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    ''', (token,))
    row = cursor.fetchone()
    conn.close()
    return row


def delete_session(token):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM sessions WHERE token = ?', (token,))
    conn.commit()
    conn.close()
