# ============================================
# Day 10: chat_service.py
# Everything about a single user's own chats: create, list,
# save/read messages, search, delete, and analytics.
# (This is the Day 7-8 logic, pulled out of chatbot.py.)
# ============================================

import secrets

from database import get_connection


def create_chat(user_id, title, personality):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO chats (user_id, title, personality) VALUES (?, ?, ?)',
                   (user_id, title, personality))
    chat_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return chat_id


def get_user_chats(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, personality, created_at, is_public FROM chats
        WHERE user_id = ? ORDER BY created_at DESC
    ''', (user_id,))
    chats = cursor.fetchall()
    conn.close()
    return chats


def get_chat_owner(chat_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM chats WHERE id = ?', (chat_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def save_message(chat_id, role, content):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)',
                   (chat_id, role, content))
    conn.commit()
    conn.close()


def get_chat_history(chat_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT role, content FROM messages WHERE chat_id = ? ORDER BY timestamp ASC',
                   (chat_id,))
    messages = cursor.fetchall()
    conn.close()
    return messages


def delete_chat(chat_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM comments WHERE chat_id = ?', (chat_id,))
    cursor.execute('DELETE FROM likes WHERE chat_id = ?', (chat_id,))
    cursor.execute('DELETE FROM messages WHERE chat_id = ?', (chat_id,))
    cursor.execute('DELETE FROM chats WHERE id = ?', (chat_id,))
    conn.commit()
    conn.close()


# ---- search across all of a user's own chats + messages ----

def search_messages(user_id, query):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT c.id, c.title, c.personality, m.content, m.role
        FROM messages m
        JOIN chats c ON m.chat_id = c.id
        WHERE c.user_id = ? AND m.content LIKE ?
        ORDER BY m.timestamp DESC
    ''', (user_id, f'%{query}%'))
    results = cursor.fetchall()
    conn.close()
    return results


# ---- analytics ----

def get_analytics(user_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT COUNT(*) FROM chats WHERE user_id = ?', (user_id,))
    total_chats = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM messages m JOIN chats c ON m.chat_id = c.id WHERE c.user_id = ?
    ''', (user_id,))
    total_messages = cursor.fetchone()[0]

    cursor.execute('''
        SELECT c.personality, COUNT(*) FROM chats c WHERE c.user_id = ? GROUP BY c.personality
    ''', (user_id,))
    personality_counts = cursor.fetchall()

    cursor.execute('''
        SELECT m.content FROM messages m JOIN chats c ON m.chat_id = c.id
        WHERE c.user_id = ? AND m.role = 'assistant'
    ''', (user_id,))
    assistant_msgs = [r[0] for r in cursor.fetchall()]

    cursor.execute('''
        SELECT DATE(m.timestamp), COUNT(*) FROM messages m JOIN chats c ON m.chat_id = c.id
        WHERE c.user_id = ? GROUP BY DATE(m.timestamp) ORDER BY DATE(m.timestamp)
    ''', (user_id,))
    daily_counts = cursor.fetchall()

    # ---- NEW for Day 9: how much love has this user's public work gotten ----
    cursor.execute('''
        SELECT COUNT(*) FROM likes l JOIN chats c ON l.chat_id = c.id WHERE c.user_id = ?
    ''', (user_id,))
    likes_received = cursor.fetchone()[0]

    cursor.execute('''
        SELECT COUNT(*) FROM comments cm JOIN chats c ON cm.chat_id = c.id WHERE c.user_id = ?
    ''', (user_id,))
    comments_received = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM chats WHERE user_id = ? AND is_public = 1', (user_id,))
    public_chats = cursor.fetchone()[0]

    conn.close()

    avg_response_length = (
        sum(len(m.split()) for m in assistant_msgs) / len(assistant_msgs)
        if assistant_msgs else 0
    )

    return {
        "total_chats": total_chats,
        "total_messages": total_messages,
        "personality_counts": personality_counts,
        "avg_response_length": avg_response_length,
        "daily_counts": daily_counts,
        "likes_received": likes_received,
        "comments_received": comments_received,
        "public_chats": public_chats,
    }
