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
#
# UPDATED AGAIN: the remote Turso connection (Hrana/HTTP) can
# drop its "stream" if a single connection is kept open across
# many sequential statements, causing
# `ValueError: Hrana: stream not found`. init_database() now
# opens a FRESH connection for every single statement, which
# sidesteps that entirely — a little slower at startup, but
# startup only happens once per app boot, so it's fine.
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


def _run(sql, params=None, ignore_errors=False, retries=3):
    """Run ONE statement on its OWN fresh connection + commit + close.
    Avoids the Turso/Hrana 'stream not found' error that happens when a
    single connection is reused across many statements. Retries a few
    times on transient network hiccups."""
    last_err = None
    for attempt in range(retries):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(sql, params or ())
            conn.commit()
            conn.close()
            return
        except Exception as e:
            last_err = e
            continue
    if not ignore_errors:
        raise last_err


def _query(sql, params=None, retries=3):
    """Run ONE read query on its own fresh connection and return fetchall()."""
    last_err = None
    for attempt in range(retries):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            conn.close()
            return rows
        except Exception as e:
            last_err = e
            continue
    raise last_err


_already_initialized = False


def init_database():
    # Streamlit reruns the WHOLE script on every click/interaction, and this
    # function was being called at the top of chatbot.py every single time —
    # hammering Turso with 20+ fresh network requests per click, which is
    # both slow and triggers "stream not found" errors under load.
    # A Python module is only imported/executed ONCE per running process,
    # so this module-level flag correctly persists across every Streamlit
    # rerun and every user session in this container — the 20+ statements
    # below now really do run only once per app boot.
    global _already_initialized
    if _already_initialized:
        return
    _already_initialized = True

    _run('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    _run('''
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

    _run('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats (id)
        )
    ''')

    _run('''
        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    _run('''
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

    _run('''
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

    _run('''
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

    _run('''
        CREATE TABLE IF NOT EXISTS site_stats (
            stat_key TEXT PRIMARY KEY,
            stat_value INTEGER NOT NULL DEFAULT 0
        )
    ''')
    _run("INSERT OR IGNORE INTO site_stats (stat_key, stat_value) VALUES ('total_visits', 0)")
    _run("INSERT OR IGNORE INTO site_stats (stat_key, stat_value) VALUES ('total_clicks', 0)")

    _run('''
        CREATE TABLE IF NOT EXISTS profile_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_username TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'Direct',
            viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # ---- lightweight migration: add columns if an old DB already exists ----
    _run("ALTER TABLE chats ADD COLUMN is_public INTEGER DEFAULT 0", ignore_errors=True)
    _run("ALTER TABLE chats ADD COLUMN share_token TEXT", ignore_errors=True)

    # ---- migration: fix profile_views if an older/wrong schema exists ----
    try:
        _query("SELECT profile_username FROM profile_views LIMIT 1")
    except Exception:
        _run("DROP TABLE IF EXISTS profile_views", ignore_errors=True)
        _run('''
            CREATE TABLE profile_views (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                profile_username TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'Direct',
                viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''', ignore_errors=True)
