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
    except sqlite3.IntegrityError:
        return False, "USERNAME_EXISTS"
    except Exception as e:
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
