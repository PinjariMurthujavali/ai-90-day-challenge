# ============================================
# Day 13: GraphQL API Implementation
# ============================================

import graphene
import sqlite3
from datetime import datetime
from functools import lru_cache

DB_FILE = "chatbot.db"

# ============================================
# GRAPHQL TYPES
# ============================================

class UserType(graphene.ObjectType):
    """User GraphQL type"""
    id = graphene.Int()
    username = graphene.String()
    email = graphene.String()
    created_at = graphene.String()
    total_chats = graphene.Int()
    total_messages = graphene.Int()
    rank = graphene.Int()

class ChatType(graphene.ObjectType):
    """Chat GraphQL type"""
    id = graphene.Int()
    title = graphene.String()
    personality = graphene.String()
    user_id = graphene.Int()
    user = graphene.Field(UserType)
    message_count = graphene.Int()
    created_at = graphene.String()
    updated_at = graphene.String()

class MessageType(graphene.ObjectType):
    """Message GraphQL type"""
    id = graphene.Int()
    chat_id = graphene.Int()
    role = graphene.String()
    content = graphene.String()
    timestamp = graphene.String()

class LeaderboardEntryType(graphene.ObjectType):
    """Leaderboard entry type"""
    rank = graphene.Int()
    user_id = graphene.Int()
    username = graphene.String()
    chats = graphene.Int()
    messages = graphene.Int()
    score = graphene.Float()

class TrendingChatType(graphene.ObjectType):
    """Trending chat type"""
    chat_id = graphene.Int()
    title = graphene.String()
    personality = graphene.String()
    author = graphene.String()
    activity_score = graphene.Float()
    engagement_rate = graphene.Float()
    trending_position = graphene.Int()

class AnalyticsType(graphene.ObjectType):
    """Platform analytics type"""
    total_users = graphene.Int()
    total_chats = graphene.Int()
    total_messages = graphene.Int()
    avg_messages_per_chat = graphene.Float()
    active_users_today = graphene.Int()
    personality_breakdown = graphene.JSONString()

class SearchResultType(graphene.ObjectType):
    """Search result type"""
    chat_id = graphene.Int()
    title = graphene.String()
    author = graphene.String()
    relevance_score = graphene.Float()
    snippet = graphene.String()

# ============================================
# GRAPHQL QUERIES
# ============================================

class Query(graphene.ObjectType):
    """GraphQL Query root"""
    
    # User queries
    user = graphene.Field(UserType, id=graphene.Int())
    users = graphene.List(UserType, limit=graphene.Int(default_value=50))
    
    # Chat queries
    chat = graphene.Field(ChatType, id=graphene.Int())
    user_chats = graphene.List(ChatType, user_id=graphene.Int())
    all_chats = graphene.List(ChatType, limit=graphene.Int(default_value=100))
    
    # Message queries
    chat_messages = graphene.List(MessageType, chat_id=graphene.Int())
    message = graphene.Field(MessageType, id=graphene.Int())
    
    # Leaderboard
    leaderboard = graphene.List(LeaderboardEntryType, limit=graphene.Int(default_value=50))
    user_rank = graphene.Field(LeaderboardEntryType, user_id=graphene.Int())
    
    # Trending
    trending = graphene.List(TrendingChatType, limit=graphene.Int(default_value=20))
    trending_by_personality = graphene.List(
        TrendingChatType,
        personality=graphene.String(),
        limit=graphene.Int(default_value=10)
    )
    
    # Search
    search = graphene.List(
        SearchResultType,
        query=graphene.String(required=True),
        limit=graphene.Int(default_value=50)
    )
    
    # Analytics
    analytics = graphene.Field(AnalyticsType)
    user_analytics = graphene.Field(AnalyticsType, user_id=graphene.Int())
    
    # Health check
    health = graphene.String()

    # ========== RESOLVERS ==========

    def resolve_user(self, info, id):
        """Get single user"""
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.id, u.username, u.email, u.created_at,
                   COUNT(c.id) as total_chats,
                   COUNT(m.id) as total_messages
            FROM users u
            LEFT JOIN chats c ON u.id = c.user_id
            LEFT JOIN messages m ON c.id = m.chat_id
            WHERE u.id = ?
            GROUP BY u.id
        ''', (id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if not user:
            return None
        
        return UserType(
            id=user['id'],
            username=user['username'],
            email=user['email'],
            created_at=user['created_at'],
            total_chats=user['total_chats'] or 0,
            total_messages=user['total_messages'] or 0
        )

    def resolve_users(self, info, limit=50):
        """Get all users"""
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.id, u.username, u.email, u.created_at,
                   COUNT(c.id) as total_chats,
                   COUNT(m.id) as total_messages
            FROM users u
            LEFT JOIN chats c ON u.id = c.user_id
            LEFT JOIN messages m ON c.id = m.chat_id
            GROUP BY u.id
            LIMIT ?
        ''', (limit,))
        
        users = cursor.fetchall()
        conn.close()
        
        return [
            UserType(
                id=u['id'],
                username=u['username'],
                email=u['email'],
                created_at=u['created_at'],
                total_chats=u['total_chats'] or 0,
                total_messages=u['total_messages'] or 0
            )
            for u in users
        ]

    def resolve_chat(self, info, id):
        """Get single chat"""
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT c.id, c.title, c.personality, c.user_id,
                   u.username, c.created_at, c.updated_at,
                   COUNT(m.id) as message_count
            FROM chats c
            LEFT JOIN users u ON c.user_id = u.id
            LEFT JOIN messages m ON c.id = m.chat_id
            WHERE c.id = ?
            GROUP BY c.id
        ''', (id,))
        
        chat = cursor.fetchone()
        conn.close()
        
        if not chat:
            return None
        
        user = UserType(username=chat['username'])
        
        return ChatType(
            id=chat['id'],
            title=chat['title'],
            personality=chat['personality'],
            user_id=chat['user_id'],
            user=user,
            message_count=chat['message_count'] or 0,
            created_at=chat['created_at'],
            updated_at=chat['updated_at']
        )

    def resolve_user_chats(self, info, user_id):
        """Get chats for specific user"""
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT c.id, c.title, c.personality, c.user_id,
                   u.username, c.created_at, c.updated_at,
                   COUNT(m.id) as message_count
            FROM chats c
            LEFT JOIN users u ON c.user_id = u.id
            LEFT JOIN messages m ON c.id = m.chat_id
            WHERE c.user_id = ?
            GROUP BY c.id
            ORDER BY c.created_at DESC
        ''', (user_id,))
        
        chats = cursor.fetchall()
        conn.close()
        
        return [
            ChatType(
                id=c['id'],
                title=c['title'],
                personality=c['personality'],
                user_id=c['user_id'],
                user=UserType(username=c['username']),
                message_count=c['message_count'] or 0,
                created_at=c['created_at'],
                updated_at=c['updated_at']
            )
            for c in chats
        ]

    def resolve_chat_messages(self, info, chat_id):
        """Get messages from chat"""
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, chat_id, role, content, timestamp
            FROM messages
            WHERE chat_id = ?
            ORDER BY timestamp ASC
        ''', (chat_id,))
        
        messages = cursor.fetchall()
        conn.close()
        
        return [
            MessageType(
                id=m['id'],
                chat_id=m['chat_id'],
                role=m['role'],
                content=m['content'],
                timestamp=m['timestamp']
            )
            for m in messages
        ]

    def resolve_leaderboard(self, info, limit=50):
        """Get leaderboard"""
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT u.id, u.username,
                   COUNT(c.id) as chats,
                   COUNT(m.id) as messages,
                   (COUNT(m.id) * 10 + COUNT(c.id) * 5) as score
            FROM users u
            LEFT JOIN chats c ON u.id = c.user_id
            LEFT JOIN messages m ON c.id = m.chat_id
            GROUP BY u.id
            ORDER BY score DESC
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            LeaderboardEntryType(
                rank=i+1,
                user_id=r['id'],
                username=r['username'],
                chats=r['chats'] or 0,
                messages=r['messages'] or 0,
                score=float(r['score'] or 0)
            )
            for i, r in enumerate(results)
        ]

    def resolve_trending(self, info, limit=20):
        """Get trending chats"""
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT c.id, c.title, c.personality, u.username,
                   COUNT(m.id) as message_count,
                   (COUNT(m.id) * 2.5) as activity_score
            FROM chats c
            LEFT JOIN users u ON c.user_id = u.id
            LEFT JOIN messages m ON c.id = m.chat_id
            GROUP BY c.id
            ORDER BY activity_score DESC
            LIMIT ?
        ''', (limit,))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            TrendingChatType(
                chat_id=r['id'],
                title=r['title'],
                personality=r['personality'],
                author=r['username'],
                activity_score=float(r['activity_score'] or 0),
                engagement_rate=float((r['message_count'] or 0) / 100),
                trending_position=i+1
            )
            for i, r in enumerate(results)
        ]

    def resolve_search(self, info, query, limit=50):
        """Search chats and messages"""
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        search_query = f"%{query}%"
        
        cursor.execute('''
            SELECT c.id, c.title, u.username, m.content,
                   CASE 
                       WHEN c.title LIKE ? THEN 1.0
                       WHEN m.content LIKE ? THEN 0.5
                       ELSE 0.3
                   END as relevance_score
            FROM chats c
            LEFT JOIN users u ON c.user_id = u.id
            LEFT JOIN messages m ON c.id = m.chat_id
            WHERE c.title LIKE ? OR m.content LIKE ?
            ORDER BY relevance_score DESC
            LIMIT ?
        ''', (search_query, search_query, search_query, search_query, limit))
        
        results = cursor.fetchall()
        conn.close()
        
        return [
            SearchResultType(
                chat_id=r['id'],
                title=r['title'],
                author=r['username'],
                relevance_score=float(r['relevance_score']),
                snippet=r['content'][:100] if r['content'] else ""
            )
            for r in results
        ]

    def resolve_analytics(self, info):
        """Get platform analytics"""
        conn = sqlite3.connect(DB_FILE)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as count FROM users')
        total_users = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM chats')
        total_chats = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM messages')
        total_messages = cursor.fetchone()['count']
        
        cursor.execute('''
            SELECT personality, COUNT(*) as count
            FROM chats
            GROUP BY personality
        ''')
        personality_data = dict(cursor.fetchall())
        
        conn.close()
        
        avg_per_chat = total_messages / total_chats if total_chats > 0 else 0
        
        return AnalyticsType(
            total_users=total_users,
            total_chats=total_chats,
            total_messages=total_messages,
            avg_messages_per_chat=avg_per_chat,
            active_users_today=total_users,
            personality_breakdown=personality_data
        )

    def resolve_health(self, info):
        """Health check"""
        return f"GraphQL API healthy at {datetime.now().isoformat()}"


# ============================================
# GRAPHQL SCHEMA
# ============================================

schema = graphene.Schema(query=Query)
