# ============================================
# Day 10: notification_service.py  (NEW FILE)
# Tells a chat owner when someone likes or comments on
# their public chat. Powers the 🔔 bell in the header.
# ============================================

from database import get_connection


def _ensure_table():
    """Defensive safety net: creates the notifications table on its own if
    the deployed database.py happens to be older than this file (e.g. a
    partial deploy where only some files got pushed). Cheap no-op once
    the table already exists."""
    conn = get_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            from_user_id INTEGER NOT NULL,
            chat_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


_ensure_table()


def create_notification(user_id, from_user_id, chat_id, ntype, message):
    """Never notify yourself about your own activity on your own chat."""
    if user_id == from_user_id:
        return
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO notifications (user_id, from_user_id, chat_id, type, message)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, from_user_id, chat_id, ntype, message))
    conn.commit()
    conn.close()


def get_notifications(user_id, limit=25):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT n.id, n.type, n.message, n.is_read, n.created_at, n.chat_id, u.username
        FROM notifications n
        JOIN users u ON n.from_user_id = u.id
        WHERE n.user_id = ?
        ORDER BY n.created_at DESC
        LIMIT ?
    ''', (user_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_unread_count(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0', (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def mark_all_read(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()


def mark_read(notification_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE notifications SET is_read = 1 WHERE id = ?', (notification_id,))
    conn.commit()
    conn.close()
