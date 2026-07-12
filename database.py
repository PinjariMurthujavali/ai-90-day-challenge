# ============================================
# Day 10: database.py
# Central SQLite connection + schema for the whole app.
# Split out of the old single chatbot.py so each feature
# area (auth / chat / social) can own its own queries.
# ============================================

import sqlite3

DB_FILE = "chatbot.db"


def get_connection():
    """Single place that opens a DB connection so every module
    talks to the same file with the same settings."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON")
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

    # ---- lightweight migration: add columns if an old DB file exists ----
    existing_cols = [row[1] for row in cursor.execute("PRAGMA table_info(chats)")]
    if "is_public" not in existing_cols:
        cursor.execute("ALTER TABLE chats ADD COLUMN is_public INTEGER DEFAULT 0")
    if "share_token" not in existing_cols:
        cursor.execute("ALTER TABLE chats ADD COLUMN share_token TEXT")

    conn.commit()
    conn.close()
