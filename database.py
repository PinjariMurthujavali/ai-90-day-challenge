# ============================================
# Day 12: database.py
# Central SQLite connection + schema for the whole app.
# Split out of the old single chatbot.py so each feature
# area (auth / chat / social) can own its own queries.
#
# UPDATED: Streamlit Community Cloud does NOT guarantee local
# file storage persists across redeploys/reboots — every git
# push can wipe the local chatbot.db file, deleting all users.
# Fix: connect to a Turso cloud database (SQLite-compatible,
# free tier) whenever TURSO_DATABASE_URL / TURSO_AUTH_TOKEN are
# configured in Streamlit secrets. Falls back to the old local
# file automatically when running on your own machine without
# those secrets set, so local dev still works unchanged.
# ============================================

import sqlite3

DB_FILE = "chatbot.db"


def get_connection():
    """Single place that opens a DB connection so every module
    talks to the same database with the same settings.

    Uses Turso (persistent cloud SQLite) in production when secrets
    are configured; falls back to a local file otherwise."""
    try:
        import streamlit as st
        turso_url = st.secrets.get("TURSO_DATABASE_URL")
        turso_token = st.secrets.get("TURSO_AUTH_TOKEN")
    except Exception:
        turso_url = None
        turso_token = None

    if turso_url and turso_token:
        import libsql
        conn = libsql.connect(database=turso_url, auth_token=turso_token)
    else:
        conn = sqlite3.connect(DB_FILE)

    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass
    return conn


def init_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ---- chats now carry an is_public flag + a share_token for Day 9 ----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT,
            personality TEXT DEFAULT 'mentor',
            is_public INTEGER DEFAULT 0,
            share_token TEXT UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats (id)
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # ---- NEW for Day 9: likes on public chats ----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats (id),
            FOREIGN KEY (user_id) REFERENCES users (id),
            UNIQUE (chat_id, user_id)
        )
    ''')

    # ---- NEW for Day 9: comments on public chats ----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # ---- NEW for Day 10: notifications (likes/comments on your public chats) ----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            from_user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (from_user_id) REFERENCES users (id),
            FOREIGN KEY (chat_id) REFERENCES chats (id)
        )
    ''')

    # ---- NEW: site-wide visit + click counters (permanent, survives restarts) ----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS site_stats (
            stat_key TEXT PRIMARY KEY,
            stat_value INTEGER NOT NULL DEFAULT 0
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO site_stats (stat_key, stat_value) VALUES ('total_visits', 0)")
    cursor.execute("INSERT OR IGNORE INTO site_stats (stat_key, stat_value) VALUES ('total_clicks', 0)")

    # ---- NEW: profile views with source tracking (permanent) ----
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profile_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_username TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'Direct',
            viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ---- lightweight migration: add columns if an old DB already exists ----
    # Turso/remote connections don't reliably support PRAGMA table_info(),
    # so instead we just try the ALTER TABLE and silently ignore the error
    # if the column already exists. This works the same way on both a
    # fresh Turso database and an older local sqlite file.
    for alter_sql in [
        "ALTER TABLE chats ADD COLUMN is_public INTEGER DEFAULT 0",
        "ALTER TABLE chats ADD COLUMN share_token TEXT",
    ]:
        try:
            cursor.execute(alter_sql)
        except Exception:
            pass

    # ---- migration: fix profile_views if an older/wrong schema exists ----
    # Try a query that only works on the NEW schema; if it fails, the old
    # (wrong-column) table is still there, so drop and recreate it.
    try:
        cursor.execute("SELECT profile_username FROM profile_views LIMIT 1")
    except Exception:
        try:
            cursor.execute("DROP TABLE IF EXISTS profile_views")
            cursor.execute('''
                CREATE TABLE profile_views (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_username TEXT NOT NULL,
                    source TEXT NOT NULL DEFAULT 'Direct',
                    viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        except Exception:
            pass

    conn.commit()
    conn.close()
