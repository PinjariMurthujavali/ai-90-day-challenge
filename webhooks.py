# ============================================
# Day 12: Webhooks + Real-time Event System
# ============================================

import json
import requests
from datetime import datetime
from typing import Dict, List
import sqlite3
from functools import wraps
import hashlib
import hmac

DB_FILE = "chatbot.db"

# ============================================
# WEBHOOK MANAGEMENT
# ============================================

class WebhookManager:
    """Manages webhook subscriptions and event firing"""
    
    def __init__(self):
        self.init_webhook_db()
    
    def init_webhook_db(self):
        """Create webhooks table"""
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webhooks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                url TEXT NOT NULL,
                active BOOLEAN DEFAULT 1,
                secret TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS webhook_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                webhook_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status INTEGER,
                response TEXT,
                attempted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (webhook_id) REFERENCES webhooks (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def subscribe(self, user_id: int, event_type: str, url: str, secret: str = None) -> int:
        """Subscribe to webhook events"""
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO webhooks (user_id, event_type, url, secret)
            VALUES (?, ?, ?, ?)
        ''', (user_id, event_type, url, secret))
        
        webhook_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return webhook_id
    
    def unsubscribe(self, webhook_id: int):
        """Unsubscribe from webhook"""
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE webhooks SET active = 0 WHERE id = ?
        ''', (webhook_id,))
        
        conn.commit()
        conn.close()
    
    def get_webhooks(self, user_id: int, event_type: str = None) -> List[Dict]:
        """Get user's webhooks"""
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        if event_type:
            cursor.execute('''
                SELECT id, event_type, url, active, created_at
                FROM webhooks
                WHERE user_id = ? AND event_type = ? AND active = 1
            ''', (user_id, event_type))
        else:
            cursor.execute('''
                SELECT id, event_type, url, active, created_at
                FROM webhooks
                WHERE user_id = ? AND active = 1
            ''', (user_id,))
        
        webhooks = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": w[0],
                "event_type": w[1],
                "url": w[2],
                "active": w[3],
                "created_at": w[4]
            }
            for w in webhooks
        ]
    
    def generate_signature(self, payload: str, secret: str) -> str:
        """Generate HMAC signature for webhook"""
        
        return hmac.new(
            secret.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def fire_event(self, event_type: str, payload: Dict, user_id: int = None):
        """Fire webhook events"""
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        # Get all webhooks for this event
        if user_id:
            cursor.execute('''
                SELECT id, url, secret FROM webhooks
                WHERE event_type = ? AND user_id = ? AND active = 1
            ''', (event_type, user_id))
        else:
            cursor.execute('''
                SELECT id, url, secret FROM webhooks
                WHERE event_type = ? AND active = 1
            ''', (event_type,))
        
        webhooks = cursor.fetchall()
        conn.close()
        
        payload_str = json.dumps(payload)
        
        for webhook_id, url, secret in webhooks:
            try:
                headers = {
                    "Content-Type": "application/json",
                    "X-Webhook-Event": event_type,
                    "X-Webhook-Timestamp": datetime.now().isoformat()
                }
                
                # Add signature if secret exists
                if secret:
                    signature = self.generate_signature(payload_str, secret)
                    headers["X-Webhook-Signature"] = f"sha256={signature}"
                
                # Send webhook
                response = requests.post(
                    url,
                    data=payload_str,
                    headers=headers,
                    timeout=10
                )
                
                status = response.status_code
                response_text = response.text[:500]  # Store first 500 chars
                
            except Exception as e:
                status = 0
                response_text = str(e)[:500]
            
            # Log webhook event
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO webhook_events 
                (webhook_id, event_type, payload, status, response)
                VALUES (?, ?, ?, ?, ?)
            ''', (webhook_id, event_type, payload_str, status, response_text))
            
            conn.commit()
            conn.close()

# ============================================
# EVENT TYPES
# ============================================

class Events:
    """Event type constants"""
    
    # Chat events
    CHAT_CREATED = "chat.created"
    CHAT_DELETED = "chat.deleted"
    
    # Message events
    MESSAGE_SENT = "message.sent"
    MESSAGE_RECEIVED = "message.received"
    
    # User events
    USER_REGISTERED = "user.registered"
    USER_LOGGED_IN = "user.logged_in"
    
    # Social events
    CHAT_LIKED = "chat.liked"
    COMMENT_ADDED = "comment.added"
    
    # System events
    LEADERBOARD_UPDATED = "leaderboard.updated"
    TRENDING_CHANGED = "trending.changed"

# ============================================
# EMAIL NOTIFICATION SERVICE
# ============================================

class EmailService:
    """Handles email notifications"""
    
    def __init__(self, smtp_server: str, smtp_port: int, sender_email: str, password: str):
        """
        Initialize email service
        
        Example with Gmail:
        EmailService(
            "smtp.gmail.com",
            587,
            "your-email@gmail.com",
            "your-app-password"
        )
        """
        
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.sender_email = sender_email
        self.password = password
    
    def send_email(self, recipient: str, subject: str, body: str, html: bool = False) -> bool:
        """Send email"""
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = recipient
            
            mime_type = "html" if html else "plain"
            message.attach(MIMEText(body, mime_type))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.password)
                server.sendmail(self.sender_email, recipient, message.as_string())
            
            return True
            
        except Exception as e:
            print(f"Email error: {str(e)}")
            return False
    
    def send_welcome_email(self, user_email: str, username: str) -> bool:
        """Send welcome email"""
        
        subject = "Welcome to Murthu AI Chatbot!"
        body = f"""
        <html>
            <body>
                <h1>Welcome, {username}! 🎉</h1>
                <p>Your account has been created successfully.</p>
                <p>Start chatting now: <a href="https://your-app.com">Launch App</a></p>
                <p>Best,<br>The Murthu Team</p>
            </body>
        </html>
        """
        
        return self.send_email(user_email, subject, body, html=True)
    
    def send_activity_digest(self, user_email: str, username: str, stats: Dict) -> bool:
        """Send daily activity digest"""
        
        subject = f"Your Daily AI Chatbot Digest - {datetime.now().strftime('%Y-%m-%d')}"
        body = f"""
        <html>
            <body>
                <h2>Hi {username}! 👋</h2>
                <p>Here's your activity summary:</p>
                <ul>
                    <li>Total Chats: {stats.get('total_chats', 0)}</li>
                    <li>Messages Today: {stats.get('messages_today', 0)}</li>
                    <li>Top Personality: {stats.get('top_personality', 'N/A')}</li>
                </ul>
                <p><a href="https://your-app.com/dashboard">View Full Dashboard</a></p>
            </body>
        </html>
        """
        
        return self.send_email(user_email, subject, body, html=True)
    
    def send_notification_email(self, user_email: str, title: str, message: str) -> bool:
        """Send general notification"""
        
        subject = f"Notification: {title}"
        body = f"""
        <html>
            <body>
                <h3>{title}</h3>
                <p>{message}</p>
                <p><a href="https://your-app.com">Go to App</a></p>
            </body>
        </html>
        """
        
        return self.send_email(user_email, subject, body, html=True)

# ============================================
# EVENT BUS
# ============================================

class EventBus:
    """Central event management"""
    
    def __init__(self, email_service: EmailService = None):
        self.webhook_manager = WebhookManager()
        self.email_service = email_service
        self.handlers = {}
    
    def subscribe_handler(self, event_type: str, handler):
        """Subscribe to event"""
        
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        
        self.handlers[event_type].append(handler)
    
    def emit(self, event_type: str, payload: Dict, user_id: int = None):
        """Emit event"""
        
        # Fire webhooks
        self.webhook_manager.fire_event(event_type, payload, user_id)
        
        # Call local handlers
        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                try:
                    handler(payload)
                except Exception as e:
                    print(f"Handler error: {str(e)}")

# ============================================
# USAGE EXAMPLE
# ============================================

"""
# Initialize
email_service = EmailService(
    "smtp.gmail.com",
    587,
    "your-email@gmail.com",
    "your-app-password"
)

event_bus = EventBus(email_service)

# Subscribe to events
def on_chat_created(payload):
    print(f"Chat created: {payload}")

event_bus.subscribe_handler(Events.CHAT_CREATED, on_chat_created)

# Setup webhook
webhook_manager = event_bus.webhook_manager
webhook_id = webhook_manager.subscribe(
    user_id=1,
    event_type=Events.MESSAGE_SENT,
    url="https://your-webhook-receiver.com/webhook",
    secret="your-secret"
)

# Emit events
event_bus.emit(Events.USER_REGISTERED, {
    "user_id": 1,
    "username": "murthu",
    "timestamp": datetime.now().isoformat()
}, user_id=1)

# Send email
email_service.send_welcome_email("user@example.com", "Murthu")
"""
