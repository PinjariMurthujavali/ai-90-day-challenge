"""
DAY 27: Database Query Optimization
=====================================
- Slow query detection (timing decorator)
- EXPLAIN QUERY PLAN analyzer
- Auto-index recommendation + creation
- Before/after benchmark report
"""

import sqlite3
import time
import functools
import logging
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("query_optimizer")

DB_PATH = "chatbot.db"
SLOW_QUERY_THRESHOLD_MS = 50

slow_query_log = []


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def track_query(label=""):
    """Decorator to measure execution time of any DB function."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            if elapsed_ms > SLOW_QUERY_THRESHOLD_MS:
                slow_query_log.append((label or func.__name__, elapsed_ms))
                logger.warning(f"🐌 SLOW QUERY [{label or func.__name__}]: {elapsed_ms:.2f} ms")
            else:
                logger.info(f"⚡ [{label or func.__name__}]: {elapsed_ms:.2f} ms")
            return result
        return wrapper
    return decorator


def explain_query(query, params=()):
    """Return EXPLAIN QUERY PLAN output for a given SQL query."""
    with get_connection() as conn:
        plan = conn.execute(f"EXPLAIN QUERY PLAN {query}", params).fetchall()
        return [dict(row) for row in plan]


def uses_full_table_scan(plan):
    return any("SCAN" in row["detail"] and "USING INDEX" not in row["detail"] for row in plan)


# ---- Common heavy queries in this app ----
QUERIES = {
    "messages_by_chat": "SELECT * FROM messages WHERE chat_id = ?",
    "chats_by_user": "SELECT * FROM chats WHERE user_id = ? ORDER BY created_at DESC",
    "comments_by_chat": "SELECT * FROM comments WHERE chat_id = ?",
    "likes_by_chat": "SELECT * FROM likes WHERE chat_id = ?",
    "sessions_by_user": "SELECT * FROM sessions WHERE user_id = ?",
    "notifications_unread": "SELECT * FROM notifications WHERE user_id = ? AND is_read = 0",
}

# ---- Recommended indexes (safe, additive, IF NOT EXISTS) ----
RECOMMENDED_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)",
    "CREATE INDEX IF NOT EXISTS idx_chats_user_id ON chats(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_chats_created_at ON chats(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_comments_chat_id ON comments(chat_id)",
    "CREATE INDEX IF NOT EXISTS idx_likes_chat_id ON likes(chat_id)",
    "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)",
    "CREATE INDEX IF NOT EXISTS idx_notifications_user_read ON notifications(user_id, is_read)",
]


@track_query("benchmark_run")
def _run_query(query, params):
    with get_connection() as conn:
        return conn.execute(query, params).fetchall()


def benchmark_all(sample_param=1):
    """Run every tracked query and log timing (before optimization)."""
    logger.info("\n=== BEFORE OPTIMIZATION ===")
    for label, q in QUERIES.items():
        params = (sample_param,)
        try:
            with_track = track_query(label)(lambda: get_connection().execute(q, params).fetchall())
            with_track()
        except Exception as e:
            logger.error(f"Skipping {label}: {e}")


def apply_indexes():
    """Create all recommended indexes."""
    with get_connection() as conn:
        for stmt in RECOMMENDED_INDEXES:
            conn.execute(stmt)
        conn.commit()
    logger.info(f"✅ Applied {len(RECOMMENDED_INDEXES)} indexes")


def analyze_all_queries():
    """Print EXPLAIN QUERY PLAN for every tracked query + flag full scans."""
    logger.info("\n=== QUERY PLAN ANALYSIS ===")
    for label, q in QUERIES.items():
        params = (1,)
        try:
            plan = explain_query(q, params)
            flag = "❌ FULL SCAN" if uses_full_table_scan(plan) else "✅ INDEXED"
            logger.info(f"{label}: {flag}")
            for row in plan:
                logger.info(f"    {row['detail']}")
        except Exception as e:
            logger.error(f"{label}: error - {e}")


def optimization_report():
    """Full before/after report: analyze -> index -> re-benchmark."""
    logger.info("#" * 50)
    logger.info("DAY 27: DATABASE QUERY OPTIMIZATION REPORT")
    logger.info("#" * 50)

    analyze_all_queries()
    benchmark_all()

    apply_indexes()

    logger.info("\n=== AFTER OPTIMIZATION ===")
    analyze_all_queries()
    benchmark_all()

    if slow_query_log:
        logger.info(f"\n⚠️ {len(slow_query_log)} slow query hits logged (>{SLOW_QUERY_THRESHOLD_MS}ms)")
    else:
        logger.info("\n🎉 No slow queries detected — all optimized!")


if __name__ == "__main__":
    optimization_report()
