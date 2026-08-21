# ============================================
# Day 13: Redis Caching Layer
# ============================================

import redis
import json
from datetime import datetime, timedelta
from functools import wraps
import hashlib

# ============================================
# REDIS CONNECTION
# ============================================

class CacheManager:
    """Redis cache management"""
    
    def __init__(self, host='localhost', port=6379, db=0):
        """Initialize Redis connection"""
        try:
            self.redis_client = redis.Redis(
                host=host,
                port=port,
                db=db,
                decode_responses=True,
                socket_connect_timeout=5
            )
            # Test connection
            self.redis_client.ping()
            self.connected = True
            print("✅ Redis connected!")
        except Exception as e:
            print(f"⚠️ Redis connection failed: {str(e)}")
            self.redis_client = None
            self.connected = False

    def get(self, key):
        """Get value from cache"""
        if not self.connected:
            return None
        
        try:
            value = self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            print(f"Cache get error: {str(e)}")
            return None

    def set(self, key, value, ttl=3600):
        """Set value in cache with TTL"""
        if not self.connected:
            return False
        
        try:
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(value)
            )
            return True
        except Exception as e:
            print(f"Cache set error: {str(e)}")
            return False

    def delete(self, key):
        """Delete cache key"""
        if not self.connected:
            return False
        
        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            print(f"Cache delete error: {str(e)}")
            return False

    def clear_pattern(self, pattern):
        """Clear all keys matching pattern"""
        if not self.connected:
            return 0
        
        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            return len(keys)
        except Exception as e:
            print(f"Cache clear error: {str(e)}")
            return 0

    def get_stats(self):
        """Get cache statistics"""
        if not self.connected:
            return {"status": "disconnected"}
        
        try:
            info = self.redis_client.info()
            return {
                "status": "connected",
                "memory_used": info.get('used_memory_human'),
                "connected_clients": info.get('connected_clients'),
                "total_commands": info.get('total_commands_processed'),
                "keyspace": self.redis_client.dbsize()
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

# ============================================
# CACHE DECORATORS
# ============================================

cache_manager = CacheManager()

def cache_query(ttl=3600):
    """Decorator to cache function results"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and args
            key = f"{func.__name__}:{hashlib.md5(str(args+tuple(kwargs.values())).encode()).hexdigest()}"
            
            # Try to get from cache
            cached = cache_manager.get(key)
            if cached is not None:
                return cached
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Store in cache
            cache_manager.set(key, result, ttl)
            
            return result
        return wrapper
    return decorator

def invalidate_cache(pattern):
    """Invalidate cache by pattern"""
    return cache_manager.clear_pattern(pattern)

# ============================================
# CACHE KEY GENERATORS
# ============================================

class CacheKeys:
    """Cache key constants"""
    
    # User cache
    USER_PREFIX = "user:"
    USER_STATS = "user_stats:{user_id}"
    USER_CHATS = "user_chats:{user_id}"
    ALL_USERS = "all_users"
    
    # Chat cache
    CHAT_PREFIX = "chat:"
    CHAT_MESSAGES = "chat_messages:{chat_id}"
    ALL_CHATS = "all_chats"
    
    # Leaderboard cache
    LEADERBOARD = "leaderboard"
    LEADERBOARD_FULL = "leaderboard:full"
    USER_RANK = "user_rank:{user_id}"
    
    # Trending cache
    TRENDING = "trending"
    TRENDING_PERSONALITY = "trending:{personality}"
    
    # Analytics cache
    ANALYTICS = "analytics"
    ANALYTICS_USER = "analytics:user:{user_id}"
    
    # Search cache
    SEARCH_PREFIX = "search:"

# ============================================
# CACHE INVALIDATION
# ============================================

class CacheInvalidator:
    """Handle cache invalidation on data changes"""
    
    @staticmethod
    def on_message_created(chat_id, user_id):
        """Invalidate cache when message is created"""
        cache_manager.delete(f"chat_messages:{chat_id}")
        cache_manager.delete(CacheKeys.CHAT_MESSAGES.format(chat_id=chat_id))
        cache_manager.delete(CacheKeys.LEADERBOARD)
        cache_manager.delete(CacheKeys.TRENDING)
        cache_manager.delete(CacheKeys.ANALYTICS)
        cache_manager.delete(CacheKeys.USER_STATS.format(user_id=user_id))

    @staticmethod
    def on_chat_created(user_id):
        """Invalidate cache when chat is created"""
        cache_manager.delete(CacheKeys.USER_CHATS.format(user_id=user_id))
        cache_manager.delete(CacheKeys.ALL_CHATS)
        cache_manager.delete(CacheKeys.LEADERBOARD)
        cache_manager.delete(CacheKeys.ANALYTICS)

    @staticmethod
    def on_user_created():
        """Invalidate cache when user is created"""
        cache_manager.delete(CacheKeys.ALL_USERS)
        cache_manager.delete(CacheKeys.LEADERBOARD)
        cache_manager.delete(CacheKeys.ANALYTICS)

    @staticmethod
    def on_engagement(chat_id, user_id):
        """Invalidate cache on engagement (like, comment)"""
        cache_manager.delete(f"chat:{chat_id}")
        cache_manager.delete(CacheKeys.TRENDING)
        cache_manager.delete(CacheKeys.USER_RANK.format(user_id=user_id))

# ============================================
# CACHE WARMING
# ============================================

def warm_cache():
    """Warm up cache with frequently accessed data"""
    # Cache leaderboard
    from api import get_leaderboard
    leaderboard = get_leaderboard()
    cache_manager.set(CacheKeys.LEADERBOARD, leaderboard, 300)
    
    # Cache trending
    trending = get_trending()
    cache_manager.set(CacheKeys.TRENDING, trending, 300)
    
    # Cache analytics
    analytics = get_analytics()
    cache_manager.set(CacheKeys.ANALYTICS, analytics, 600)
    
    print("✅ Cache warmed up!")

# ============================================
# CACHED FUNCTIONS
# ============================================

@cache_query(ttl=1800)
def get_leaderboard_cached(limit=50):
    """Cached leaderboard query"""
    from api import get_leaderboard
    return get_leaderboard(limit)

@cache_query(ttl=300)
def get_trending_cached(limit=20):
    """Cached trending query"""
    from api import get_trending
    return get_trending(limit)

@cache_query(ttl=3600)
def get_analytics_cached():
    """Cached analytics query"""
    from api import get_analytics
    return get_analytics()

@cache_query(ttl=600)
def get_user_stats_cached(user_id):
    """Cached user stats"""
    from api import get_user_stats
    return get_user_stats(user_id)

# ============================================
# CACHE STATUS
# ============================================

def get_cache_status():
    """Get cache system status"""
    return {
        "cache_system": "Redis",
        "status": "connected" if cache_manager.connected else "disconnected",
        "stats": cache_manager.get_stats()
    }
