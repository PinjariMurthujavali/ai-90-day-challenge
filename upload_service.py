# ============================================
# Day 19: upload_service.py  (NEW FILE)
# File uploads attached to a chat. Stored as base64 in the same database
# that already persists chats/messages (Turso), rather than local disk —
# see the comment on the `attachments` table in database.py for why.
#
# Size is capped (MAX_FILE_SIZE_BYTES) to keep individual DB rows small;
# this is a chat-attachment feature, not general file storage.
# ============================================

import base64

import streamlit as st

from database import get_connection

MAX_FILE_SIZE_BYTES = 3 * 1024 * 1024  # 3 MB per file
ALLOWED_EXTENSIONS = ["png", "jpg", "jpeg", "gif", "webp", "pdf", "txt", "md", "csv"]
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}


def human_size(num_bytes):
    for unit in ["B", "KB", "MB"]:
        if num_bytes < 1024:
            return f"{num_bytes:.0f} {unit}" if unit == "B" else f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"


def is_image(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in IMAGE_EXTENSIONS


def save_attachment(chat_id, user_id, filename, mime_type, data_bytes):
    if len(data_bytes) > MAX_FILE_SIZE_BYTES:
        return False, f"File too large — max {human_size(MAX_FILE_SIZE_BYTES)}."

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        return False, f"'.{ext}' isn't a supported file type."

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO attachments (chat_id, user_id, filename, mime_type, size_bytes, data_b64)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (chat_id, user_id, filename, mime_type, len(data_bytes),
         base64.b64encode(data_bytes).decode("ascii")),
    )
    conn.commit()
    conn.close()
    get_attachments_for_chat.clear()
    return True, "Uploaded!"


@st.cache_data(ttl=10)
def get_attachments_for_chat(chat_id):
    """Returns metadata only (no data_b64) — kept light since this is
    called on every chat page render. Use get_attachment_data() to fetch
    the actual bytes for one specific file only when it's displayed/downloaded."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''SELECT id, filename, mime_type, size_bytes, created_at
           FROM attachments WHERE chat_id = ? ORDER BY created_at ASC''',
        (chat_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_attachment_data(attachment_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT data_b64, mime_type, filename FROM attachments WHERE id = ?', (attachment_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None, None, None
    return base64.b64decode(row[0]), row[1], row[2]


def delete_attachment(attachment_id, requesting_user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, chat_id FROM attachments WHERE id = ?', (attachment_id,))
    row = cursor.fetchone()
    if not row or row[0] != requesting_user_id:
        conn.close()
        return False
    cursor.execute('DELETE FROM attachments WHERE id = ?', (attachment_id,))
    conn.commit()
    conn.close()
    get_attachments_for_chat.clear()
    return True
