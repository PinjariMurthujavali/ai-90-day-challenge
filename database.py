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
# UPDATED AGAIN (perf fix — this was making the whole app feel
# slow): get_connection() used to open a BRAND NEW network
# connection to Turso for every single query — and it's called
# from ~46 places across auth/chat/social/notify/stats, all of
# which fire on every Streamlit rerun (every click). That's
# 15-20+ fresh remote handshakes per interaction.
#
# Fix: get_connection() now returns ONE cached, shared connection
# per app process (per-Streamlit-session when running under
# Streamlit, via st.cache_resource) and reuses it for every query.
# Every existing call site still does `conn = get_connection()` /
# `conn.close()` exactly as before — .close() is now a safe no-op
# on the shared connection, so nothing else needed to change.
#
# To keep the earlier "Hrana: stream not found" fix (which is why
# fresh connections were introduced in the first place), the
# returned connection is self-healing: if a query fails because the
# remote Turso stream died from being idle, it transparently opens
# a fresh real connection and retries once, instead of every caller
# having to pay for a fresh connection on every single query.
# ============================================

import sqlite3

DB_FILE = "chatbot.db"


def _get_turso_secrets():
    """Reads Turso credentials from Streamlit secrets when running under
    Streamlit, or from environment variables otherwise (e.g. the Flask
    scripts / api_day13_complete.py / webhooks.py import this module too)."""
    try:
        import streamlit as st
        return st.secrets.get("TURSO_DATABASE_URL"), st.secrets.get("TURSO_AUTH_TOKEN")
    except Exception:
        import os
        return os.getenv("TURSO_DATABASE_URL"), os.getenv("TURSO_AUTH_TOKEN")


def _open_raw_connection():
    """Actually opens a new physical connection. Only called once at
    startup, and again later ONLY if the shared connection needs to
    self-heal after a dead/expired remote stream."""
    turso_url, turso_token = _get_turso_secrets()

    if turso_url and turso_token:
        import libsql
        conn = libsql.connect(database=turso_url, auth_token=turso_token)
    else:
        conn = sqlite3.connect(DB_FILE, check_same_thread=False)

    try:
        conn.execute("PRAGMA foreign_keys = ON")
    except Exception:
        pass
    return conn


class _SharedCursor:
    """Wraps a real cursor. If the underlying execute() fails because the
    remote Turso stream went stale, transparently reconnects the shared
    connection and retries the exact same statement once before giving up."""

    def __init__(self, parent):
        self._parent = parent
        self._cur = None

    def execute(self, sql, params=()):
        try:
            self._cur = self._parent._real.cursor()
            self._cur.execute(sql, params or ())
        except Exception:
            self._parent._reconnect()
            self._cur = self._parent._real.cursor()
            self._cur.execute(sql, params or ())
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def lastrowid(self):
        return self._cur.lastrowid

    @property
    def rowcount(self):
        return self._cur.rowcount


class _SharedConnection:
    """One real connection, reused for the life of the process/session.
    Existing code everywhere calls conn.close() after each query the way
    it did with the old fresh-connection-per-query design — that's kept
    working on purpose (as a no-op) so none of the 7 files that already
    call get_connection() needed to change."""

    def __init__(self):
        self._real = _open_raw_connection()

    def cursor(self):
        return _SharedCursor(self)

    def execute(self, sql, params=()):
        return self.cursor().execute(sql, params)

    def commit(self):
        try:
            self._real.commit()
        except Exception:
            self._reconnect()
            self._real.commit()

    def close(self):
        # No-op on purpose — this connection is shared/cached and stays
        # open for the next query. See module docstring above.
        pass

    def _reconnect(self):
        try:
            self._real.close()
        except Exception:
            pass
        self._real = _open_raw_connection()


# ---- caching layer: ONE shared connection per process ----
try:
    import streamlit as st

    @st.cache_resource(show_spinner=False)
    def _cached_connection():
        return _SharedConnection()

    def get_connection():
        """Single place that opens a DB connection so every module talks
        to the same database with the same settings. Cached via
        st.cache_resource so this is created ONCE per app process, not on
        every rerun/click — this is the main speed fix."""
        return _cached_connection()

except Exception:
    # Running outside Streamlit (Flask scripts, test.py, etc.) — fall back
    # to a plain module-level cached connection instead.
    _fallback_connection = None

    def get_connection():
        global _fallback_connection
        if _fallback_connection is None:
            _fallback_connection = _SharedConnection()
        return _fallback_connection


def _run(sql, params=None, ignore_errors=False, retries=3):
    """Run ONE write statement + commit using the shared connection.
    Retries a few times on transient network hiccups (self-healing
    reconnect already happens inside _SharedConnection/_SharedCursor)."""
    last_err = None
    for attempt in range(retries):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(sql, params or ())
            conn.commit()
            return
        except Exception as e:
            last_err = e
            continue
    if not ignore_errors:
        raise last_err


def _query(sql, params=None, retries=3):
    """Run ONE read query using the shared connection and return fetchall()."""
    last_err = None
    for attempt in range(retries):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute(sql, params or ())
            rows = cur.fetchall()
            return rows
        except Exception as e:
            last_err = e
            continue
    raise last_err


_already_initialized = False


def init_database():
    # Streamlit reruns the WHOLE script on every click/interaction, and this
    # function was being called at the top of chatbot.py every single time —
    # this flag makes sure the 20+ CREATE TABLE statements below only ever
    # run once per app boot, on the (now shared and fast) connection.
    global _already_initialized
    if _already_initialized:
        return
    _already_initialized = True

    _run('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Day 14: OAuth2 login (Google). Existing DBs were created with
    # password_hash NOT NULL and no oauth_* columns — ALTER TABLE ADD COLUMN
    # is the only safe way to extend an existing SQLite/Turso table without
    # a destructive rebuild, so we add the new columns defensively and
    # ignore the "duplicate column" error on every boot after the first.
    _run("ALTER TABLE users ADD COLUMN email TEXT", ignore_errors=True)
    _run("ALTER TABLE users ADD COLUMN oauth_provider TEXT", ignore_errors=True)
    _run("ALTER TABLE users ADD COLUMN oauth_id TEXT", ignore_errors=True)
    _run("ALTER TABLE users ADD COLUMN avatar_url TEXT", ignore_errors=True)

    # ---- Day 17: email notifications — opt-in, off by default so nobody
    # gets emailed without choosing to be. `email` column already exists
    # (added above for OAuth), reused here for username/password users too.
    _run("ALTER TABLE users ADD COLUMN email_notifications_enabled INTEGER DEFAULT 0", ignore_errors=True)

    # ---- Day 18: admin flag + subscription plan. Payments/Stripe come
    # later on the roadmap — for now `plan` is a manually-assigned label
    # (free / pro / enterprise) that only an admin account can change,
    # from the new Admin panel, so the plan concept and the UI for it
    # both exist ahead of real billing being wired in.
    _run("ALTER TABLE users ADD COLUMN is_admin INTEGER DEFAULT 0", ignore_errors=True)
    _run("ALTER TABLE users ADD COLUMN plan TEXT DEFAULT 'free'", ignore_errors=True)
    _run("ALTER TABLE users ADD COLUMN plan_updated_at TIMESTAMP", ignore_errors=True)

    # Older DBs were created before OAuth existed, with password_hash NOT
    # NULL — SQLite can't ALTER a column's NOT NULL constraint in place, so
    # if we detect that old constraint we rebuild the table (same trick
    # SQLite itself recommends: new table -> copy rows -> swap names).
    try:
        col_info = _query("PRAGMA table_info(users)")
        password_col = next((c for c in col_info if c[1] == "password_hash"), None)
        if password_col and password_col[3]:  # column[3] = notnull flag
            _run('''
                CREATE TABLE users_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    email TEXT,
                    oauth_provider TEXT,
                    oauth_id TEXT,
                    avatar_url TEXT
                )
            ''')
            _run('''
                INSERT INTO users_new (id, username, password_hash, created_at, email, oauth_provider, oauth_id, avatar_url)
                SELECT id, username, password_hash, created_at, email, oauth_provider, oauth_id, avatar_url FROM users
            ''')
            _run("DROP TABLE users")
            _run("ALTER TABLE users_new RENAME TO users")
    except Exception:
        pass

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

    # ---- Day 19: file uploads. Small files only (base64 stored straight in
    # the DB row) — no external object storage is configured for this
    # project, and Streamlit Cloud's filesystem is ephemeral (wiped on
    # every redeploy), so a plain local-disk save would silently lose
    # every uploaded file the next time the app restarts. Storing the
    # bytes in the same database that already survives restarts (Turso)
    # is the option that's actually durable without adding new infra.
    _run('''
        CREATE TABLE IF NOT EXISTS attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            mime_type TEXT NOT NULL,
            size_bytes INTEGER NOT NULL,
            data_b64 TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (chat_id) REFERENCES chats (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
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
