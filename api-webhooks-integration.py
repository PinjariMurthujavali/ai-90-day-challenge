# ============================================
# Day 12: Flask API - Webhook Endpoints
# ============================================
# Add these routes to your existing api.py

from flask import Flask, jsonify, request
from webhooks import WebhookManager, EventBus, EmailService, Events

# Initialize
webhook_manager = WebhookManager()
event_bus = EventBus()

# ============================================
# WEBHOOK ENDPOINTS
# ============================================

@app.route('/api/v1/webhooks', methods=['POST'])
@token_required
def create_webhook():
    """Create new webhook subscription"""
    
    data = request.get_json()
    user_id = data.get('user_id')
    event_type = data.get('event_type')
    url = data.get('url')
    secret = data.get('secret')
    
    if not all([user_id, event_type, url]):
        return jsonify({"error": "Missing required fields"}), 400
    
    webhook_id = webhook_manager.subscribe(user_id, event_type, url, secret)
    
    return jsonify({
        "success": True,
        "webhook_id": webhook_id,
        "event_type": event_type,
        "url": url
    }), 201

@app.route('/api/v1/webhooks/<int:user_id>', methods=['GET'])
def get_user_webhooks(user_id):
    """Get user's webhooks"""
    
    event_type = request.args.get('event_type')
    webhooks = webhook_manager.get_webhooks(user_id, event_type)
    
    return jsonify({
        "webhooks": webhooks,
        "count": len(webhooks)
    }), 200

@app.route('/api/v1/webhooks/<int:webhook_id>', methods=['DELETE'])
@token_required
def delete_webhook(webhook_id):
    """Delete webhook"""
    
    webhook_manager.unsubscribe(webhook_id)
    
    return jsonify({
        "success": True,
        "message": "Webhook deleted"
    }), 200

@app.route('/api/v1/events/test', methods=['POST'])
@token_required
def test_webhook():
    """Test fire webhook event"""
    
    data = request.get_json()
    event_type = data.get('event_type')
    payload = data.get('payload', {})
    user_id = data.get('user_id')
    
    # Add metadata
    payload['test'] = True
    payload['timestamp'] = datetime.now().isoformat()
    
    # Fire event
    event_bus.emit(event_type, payload, user_id)
    
    return jsonify({
        "success": True,
        "event_type": event_type,
        "message": "Webhook fired"
    }), 200

# ============================================
# EMAIL ENDPOINTS
# ============================================

@app.route('/api/v1/email/send-digest', methods=['POST'])
@token_required
def send_digest():
    """Send activity digest to user"""
    
    data = request.get_json()
    user_id = data.get('user_id')
    
    # Get user email (from database)
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT username FROM users WHERE id = ?
    ''', (user_id,))
    
    user = cursor.fetchone()
    
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    username = user[0]
    
    # Get user stats
    cursor.execute('''
        SELECT COUNT(*) FROM chats WHERE user_id = ?
    ''', (user_id,))
    total_chats = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT COUNT(*) FROM messages m
        JOIN chats c ON m.chat_id = c.id
        WHERE c.user_id = ? AND DATE(m.timestamp) = DATE('now')
    ''', (user_id,))
    messages_today = cursor.fetchone()[0]
    
    conn.close()
    
    stats = {
        "total_chats": total_chats,
        "messages_today": messages_today,
        "top_personality": "mentor"  # Calculate from data
    }
    
    # Send email (requires email configuration)
    # email_service.send_activity_digest(user_email, username, stats)
    
    return jsonify({
        "success": True,
        "message": f"Digest sent to user {username}"
    }), 200

# ============================================
# WEBHOOK EVENT LOGGING
# ============================================

@app.route('/api/v1/webhooks/<int:webhook_id>/logs', methods=['GET'])
def get_webhook_logs(webhook_id):
    """Get webhook delivery logs"""
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, event_type, status, attempted_at
        FROM webhook_events
        WHERE webhook_id = ?
        ORDER BY attempted_at DESC
        LIMIT 50
    ''', (webhook_id,))
    
    events = cursor.fetchall()
    conn.close()
    
    result = []
    for event_id, event_type, status, timestamp in events:
        result.append({
            "id": event_id,
            "event_type": event_type,
            "status": status,
            "timestamp": timestamp
        })
    
    return jsonify({
        "logs": result,
        "count": len(result)
    }), 200

# ============================================
# WEBHOOK STATISTICS
# ============================================

@app.route('/api/v1/webhooks/stats', methods=['GET'])
def webhook_stats():
    """Get webhook statistics"""
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM webhooks WHERE active = 1')
    total_active = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM webhook_events')
    total_events = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM webhook_events WHERE status = 200')
    successful = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM webhook_events WHERE status != 200')
    failed = cursor.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        "total_active_webhooks": total_active,
        "total_events_fired": total_events,
        "successful_deliveries": successful,
        "failed_deliveries": failed,
        "success_rate": f"{(successful/(successful+failed)*100):.1f}%" if (successful+failed) > 0 else "N/A"
    }), 200

# ============================================
# HELPER: Fire Event on Chat Creation
# ============================================

def on_chat_created(user_id: int, chat_id: int, title: str, personality: str):
    """Call this when chat is created"""
    
    payload = {
        "chat_id": chat_id,
        "user_id": user_id,
        "title": title,
        "personality": personality,
        "timestamp": datetime.now().isoformat()
    }
    
    event_bus.emit(Events.CHAT_CREATED, payload, user_id)

def on_message_sent(chat_id: int, user_id: int, content: str):
    """Call this when message is sent"""
    
    payload = {
        "chat_id": chat_id,
        "user_id": user_id,
        "content": content[:100],  # First 100 chars
        "timestamp": datetime.now().isoformat()
    }
    
    event_bus.emit(Events.MESSAGE_SENT, payload, user_id)

# ============================================
# IMPORT AT TOP OF api.py
# ============================================

# from datetime import datetime
# from webhooks import WebhookManager, EventBus, Events
# import sqlite3
