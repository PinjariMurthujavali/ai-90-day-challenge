# ============================================
# Day 11: REST API for AI Chatbot
# ============================================

from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import json
import secrets
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
CORS(app)  # Enable cross-origin requests (for mobile apps, etc)

DB_FILE = "chatbot.db"

# ============================================
# AUTHENTICATION MIDDLEWARE
# ============================================

def token_required(f):
    """Decorator to check API token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({"error": "Missing token"}), 401
        return f(*args, **kwargs)
    return decorated

# ============================================
# AUTH ENDPOINTS (Day 34: needed for mobile app login)
# ============================================

@app.route('/api/v1/auth/login', methods=['POST'])
def api_login():
    """Login endpoint for the mobile app. Reuses auth.py's login_user()."""
    from auth import login_user
    data = request.get_json(force=True, silent=True) or {}
    username = data.get('username')
    password = data.get('password')
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    success, user_id = login_user(username, password)
    if not success:
        return jsonify({"error": "Invalid username or password"}), 401

    # Simple bearer token (stateless placeholder — swap for JWT in production)
    token = secrets.token_hex(24)
    return jsonify({"token": token, "user_id": user_id, "username": username})


@app.route('/api/v1/auth/register', methods=['POST'])
def api_register():
    """Register endpoint for the mobile app. Reuses auth.py's register_user()."""
    from auth import register_user
    data = request.get_json(force=True, silent=True) or {}
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    success, message = register_user(username, password, email)
    if not success:
        return jsonify({"error": message}), 400
    return jsonify({"status": "registered", "message": message})

# ============================================
# LEADERBOARD ENDPOINTS
# ============================================

@app.route('/api/v1/leaderboard', methods=['GET'])
def get_leaderboard():
    """Get top users by chat activity"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Get users with most chats
    cursor.execute('''
        SELECT u.id, u.username, COUNT(c.id) as chat_count, 
               COUNT(m.id) as message_count,
               MAX(c.created_at) as last_chat
        FROM users u
        LEFT JOIN chats c ON u.id = c.user_id
        LEFT JOIN messages m ON c.id = m.chat_id
        GROUP BY u.id
        ORDER BY message_count DESC
        LIMIT 50
    ''')
    
    leaderboard = cursor.fetchall()
    conn.close()
    
    result = []
    for i, (user_id, username, chats, messages, last_chat) in enumerate(leaderboard, 1):
        result.append({
            "rank": i,
            "user_id": user_id,
            "username": username,
            "chats": chats or 0,
            "messages": messages or 0,
            "last_activity": last_chat
        })
    
    return jsonify({"leaderboard": result, "total": len(result)}), 200

@app.route('/api/v1/user/<int:user_id>/stats', methods=['GET'])
def get_user_stats(user_id):
    """Get individual user statistics"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT username FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    cursor.execute('''
        SELECT COUNT(*) FROM chats WHERE user_id = ?
    ''', (user_id,))
    total_chats = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT COUNT(*) FROM messages m
        JOIN chats c ON m.chat_id = c.id
        WHERE c.user_id = ?
    ''', (user_id,))
    total_messages = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT AVG(LENGTH(content)) FROM messages m
        JOIN chats c ON m.chat_id = c.id
        WHERE c.user_id = ? AND m.role = 'user'
    ''', (user_id,))
    avg_msg_length = cursor.fetchone()[0] or 0
    
    cursor.execute('''
        SELECT personality, COUNT(*) FROM chats
        WHERE user_id = ?
        GROUP BY personality
    ''', (user_id,))
    personalities = dict(cursor.fetchall())
    
    conn.close()
    
    return jsonify({
        "username": user[0],
        "total_chats": total_chats,
        "total_messages": total_messages,
        "avg_message_length": int(avg_msg_length),
        "personalities_used": personalities
    }), 200

# ============================================
# TRENDING ENDPOINTS
# ============================================

@app.route('/api/v1/trending', methods=['GET'])
def get_trending():
    """Get trending chats (most active in last 7 days)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    week_ago = (datetime.now() - timedelta(days=7)).isoformat()
    
    cursor.execute('''
        SELECT c.id, c.title, c.personality, u.username,
               COUNT(m.id) as message_count,
               c.created_at
        FROM chats c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN messages m ON c.id = m.chat_id AND m.timestamp > ?
        WHERE c.created_at > ?
        GROUP BY c.id
        ORDER BY message_count DESC
        LIMIT 20
    ''', (week_ago, week_ago))
    
    trending = cursor.fetchall()
    conn.close()
    
    result = []
    for chat_id, title, personality, username, msg_count, created_at in trending:
        result.append({
            "chat_id": chat_id,
            "title": title,
            "personality": personality,
            "author": username,
            "activity": msg_count or 0,
            "created_at": created_at
        })
    
    return jsonify({"trending": result}), 200

# ============================================
# CHAT ENDPOINTS
# ============================================

@app.route('/api/v1/chats/<int:user_id>', methods=['GET'])
def get_user_chats_api(user_id):
    """Get all chats for a user (API format)"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, personality, created_at FROM chats
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (user_id,))
    
    chats = cursor.fetchall()
    conn.close()
    
    result = []
    for chat_id, title, personality, created_at in chats:
        result.append({
            "id": chat_id,
            "title": title,
            "personality": personality,
            "created_at": created_at
        })
    
    return jsonify({"chats": result}), 200

@app.route('/api/v1/chat/<int:chat_id>/messages', methods=['GET'])
def get_chat_messages(chat_id):
    """Get all messages from a specific chat"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT role, content, timestamp FROM messages
        WHERE chat_id = ?
        ORDER BY timestamp ASC
    ''', (chat_id,))
    
    messages = cursor.fetchall()
    conn.close()
    
    result = []
    for role, content, timestamp in messages:
        result.append({
            "role": role,
            "content": content,
            "timestamp": timestamp
        })
    
    return jsonify({"messages": result}), 200

@app.route('/api/v1/chat/<int:chat_id>/messages', methods=['POST'])
@token_required
def send_message_api(chat_id):
    """Send a message in an existing chat and get an AI reply (mobile app)."""
    import os
    data = request.get_json(force=True, silent=True) or {}
    content = data.get('content')
    if not content:
        return jsonify({"error": "content is required"}), 400

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Save user message
    cursor.execute(
        "INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, 'user', ?, ?)",
        (chat_id, content, datetime.now().isoformat())
    )
    conn.commit()

    # Get AI reply via Groq, with full chat history for memory (falls back to a stub reply if no key configured)
    reply_text = "I'm here! (AI reply unavailable — GROQ_API_KEY not configured on this server.)"
    api_key = os.getenv("GROQ_API_KEY")
    if api_key:
        try:
            from groq import Groq
            client = Groq(api_key=api_key)

            # Pull prior messages in this chat so the model has conversation memory
            hist_cursor = conn.cursor()
            hist_cursor.execute(
                "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY timestamp ASC",
                (chat_id,)
            )
            history = [{"role": r, "content": c} for r, c in hist_cursor.fetchall()]

            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=history,
            )
            reply_text = completion.choices[0].message.content
        except Exception as e:
            reply_text = f"AI reply failed: {str(e)}"

    cursor.execute(
        "INSERT INTO messages (chat_id, role, content, timestamp) VALUES (?, 'assistant', ?, ?)",
        (chat_id, reply_text, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

    return jsonify({"reply": reply_text}), 201


@app.route('/api/v1/chat', methods=['POST'])
@token_required
def create_chat_api():
    """Create a new chat (requires auth token)"""
    data = request.get_json()
    
    user_id = data.get('user_id')
    title = data.get('title', 'Untitled')
    personality = data.get('personality', 'mentor')
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO chats (user_id, title, personality)
        VALUES (?, ?, ?)
    ''', (user_id, title, personality))
    
    chat_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    return jsonify({
        "success": True,
        "chat_id": chat_id,
        "message": "Chat created successfully"
    }), 201

# ============================================
# SEARCH ENDPOINTS
# ============================================

@app.route('/api/v1/search', methods=['GET'])
def search_api():
    """Search across all public chats"""
    query = request.args.get('q', '')
    
    if len(query) < 2:
        return jsonify({"error": "Query must be at least 2 characters"}), 400
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT c.id, c.title, c.personality, u.username,
               COUNT(m.id) as message_count
        FROM chats c
        JOIN users u ON c.user_id = u.id
        LEFT JOIN messages m ON c.id = m.chat_id
        WHERE LOWER(c.title) LIKE LOWER(?) 
           OR LOWER(m.content) LIKE LOWER(?)
        GROUP BY c.id
        LIMIT 50
    ''', (f'%{query}%', f'%{query}%'))
    
    results = cursor.fetchall()
    conn.close()
    
    data = []
    for chat_id, title, personality, username, msg_count in results:
        data.append({
            "id": chat_id,
            "title": title,
            "personality": personality,
            "author": username,
            "messages": msg_count or 0
        })
    
    return jsonify({"results": data, "count": len(data)}), 200

# ============================================
# ANALYTICS ENDPOINTS
# ============================================

@app.route('/api/v1/analytics/overview', methods=['GET'])
def analytics_overview():
    """Get overall platform analytics"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM chats')
    total_chats = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM messages')
    total_messages = cursor.fetchone()[0]
    
    cursor.execute('SELECT personality, COUNT(*) FROM chats GROUP BY personality')
    personality_stats = dict(cursor.fetchall())
    
    conn.close()
    
    return jsonify({
        "total_users": total_users,
        "total_chats": total_chats,
        "total_messages": total_messages,
        "personality_breakdown": personality_stats
    }), 200

# ============================================
# HEALTH CHECK
# ============================================

@app.route('/api/v1/health', methods=['GET'])
def health_check():
    """API health check"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0"
    }), 200

# ============================================
# ERROR HANDLERS
# ============================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint not found"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Internal server error"}), 500

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
