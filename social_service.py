# ============================================
# Day 9: social_service.py  (NEW FILE)
# The "advanced level" features: publish a chat to the
# community feed, like it, comment on it, and share it.
# ============================================

import secrets

from database import get_connection
import notification_service as notify


# ---- publish / unpublish a chat ----

def set_chat_public(chat_id, is_public):
    """Turn sharing on/off for a chat. Generates a share_token the
    first time a chat goes public so it has a stable share link."""
    conn = get_connection()
    cursor = conn.cursor()

    if is_public:
        cursor.execute('SELECT share_token FROM chats WHERE id = ?', (chat_id,))
        row = cursor.fetchone()
        token = row[0] if row and row[0] else secrets.token_urlsafe(8)
        cursor.execute('UPDATE chats SET is_public = 1, share_token = ? WHERE id = ?',
                       (token, chat_id))
    else:
        cursor.execute('UPDATE chats SET is_public = 0 WHERE id = ?', (chat_id,))

    conn.commit()
    conn.close()


def get_chat_public_info(chat_id):
    """Returns (is_public, share_token) for a chat."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_public, share_token FROM chats WHERE id = ?', (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return row if row else (0, None)


def get_chat_by_share_token(token):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.id, c.title, c.personality, c.user_id, u.username
        FROM chats c JOIN users u ON c.user_id = u.id
        WHERE c.share_token = ? AND c.is_public = 1
    ''', (token,))
    row = cursor.fetchone()
    conn.close()
    return row


# ---- likes ----

def toggle_like(chat_id, user_id):
    """Like if not already liked, unlike if already liked. Returns new liked state (bool)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM likes WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
    existing = cursor.fetchone()

    if existing:
        cursor.execute('DELETE FROM likes WHERE id = ?', (existing[0],))
        liked = False
    else:
        cursor.execute('INSERT INTO likes (chat_id, user_id) VALUES (?, ?)', (chat_id, user_id))
        liked = True

    conn.commit()
    conn.close()

    if liked:
        cursor2 = get_connection()
        owner_row = cursor2.execute('SELECT user_id, title FROM chats WHERE id = ?', (chat_id,)).fetchone()
        liker_row = cursor2.execute('SELECT username FROM users WHERE id = ?', (user_id,)).fetchone()
        cursor2.close()
        if owner_row and liker_row:
            owner_id, title = owner_row
            liker_name = liker_row[0]
            notify.create_notification(
                owner_id, user_id, chat_id, "like",
                f"❤️ {liker_name} liked your chat \"{title or 'Untitled'}\""
            )

    return liked


def has_liked(chat_id, user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM likes WHERE chat_id = ? AND user_id = ?', (chat_id, user_id))
    row = cursor.fetchone()
    conn.close()
    return row is not None


def get_like_count(chat_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM likes WHERE chat_id = ?', (chat_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ---- comments ----

def add_comment(chat_id, user_id, content):
    content = (content or "").strip()
    if not content:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO comments (chat_id, user_id, content) VALUES (?, ?, ?)',
                   (chat_id, user_id, content))
    conn.commit()
    conn.close()

    conn2 = get_connection()
    owner_row = conn2.execute('SELECT user_id, title FROM chats WHERE id = ?', (chat_id,)).fetchone()
    commenter_row = conn2.execute('SELECT username FROM users WHERE id = ?', (user_id,)).fetchone()
    conn2.close()
    if owner_row and commenter_row:
        owner_id, title = owner_row
        commenter_name = commenter_row[0]
        preview = content if len(content) <= 40 else content[:40] + "..."
        notify.create_notification(
            owner_id, user_id, chat_id, "comment",
            f"💬 {commenter_name} commented on \"{title or 'Untitled'}\": {preview}"
        )

    return True


def get_comments(chat_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT cm.id, u.username, cm.content, cm.created_at
        FROM comments cm JOIN users u ON cm.user_id = u.id
        WHERE cm.chat_id = ? ORDER BY cm.created_at ASC
    ''', (chat_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_comment_count(chat_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM comments WHERE chat_id = ?', (chat_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def delete_comment(comment_id, requesting_user_id):
    """Only the comment's author can delete it."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM comments WHERE id = ? AND user_id = ?',
                   (comment_id, requesting_user_id))
    conn.commit()
    conn.close()


# ---- NEW for Day 10: a single author's public profile ----

def get_public_chats_by_user(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.id, c.title, c.personality, c.created_at,
               COUNT(DISTINCT l.id) AS like_count,
               COUNT(DISTINCT cm.id) AS comment_count
        FROM chats c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN likes l ON l.chat_id = c.id
        LEFT JOIN comments cm ON cm.chat_id = c.id
        WHERE c.is_public = 1 AND u.username = ?
        GROUP BY c.id
        ORDER BY c.created_at DESC
    ''', (username,))
    rows = cursor.fetchall()
    conn.close()
    return rows


# ---- the public feed / "Explore" gallery ----

def get_public_feed(sort_by="popular", search_query=None):
    """Returns a list of public chats with like/comment counts and owner info.
    sort_by: 'popular' (most liked) or 'recent' (newest first)."""
    conn = get_connection()
    cursor = conn.cursor()

    base_query = '''
        SELECT c.id, c.title, c.personality, c.created_at, u.username,
               COUNT(DISTINCT l.id) AS like_count,
               COUNT(DISTINCT cm.id) AS comment_count
        FROM chats c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN likes l ON l.chat_id = c.id
        LEFT JOIN comments cm ON cm.chat_id = c.id
        WHERE c.is_public = 1
    '''
    params = []

    if search_query:
        base_query += " AND (c.title LIKE ? OR u.username LIKE ?)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    base_query += " GROUP BY c.id"
    base_query += " ORDER BY like_count DESC, c.created_at DESC" if sort_by == "popular" \
        else " ORDER BY c.created_at DESC"

    cursor.execute(base_query, params)
    rows = cursor.fetchall()
    conn.close()
    return rows
