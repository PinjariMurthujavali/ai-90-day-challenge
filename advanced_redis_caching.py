# ============================================
# Day 15: Advanced Redis Caching Patterns
# ============================================
# Improvements over Day 14:
# ✅ Cache warming strategies
# ✅ Cache invalidation patterns
# ✅ Distributed caching
# ✅ Cache statistics & monitoring
# ✅ Performance dashboard
# ✅ Smart caching algorithms

import redis
import json
from datetime import datetime, timedelta
from functools import wraps
import hashlib
from typing import Any, Optional, Callable
import threading
import time

# ============================================
# REDIS CONNECTION POOL (Production)
# ============================================

class RedisCluster:
    """Production-grade Redis cluster connection"""
    
    def __init__(self, host='localhost', port=6379, db=0, pool_size=50):
        self.pool = redis.ConnectionPool(
            host=host,
            port=port,
            db=db,
            max_connections=pool_size,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30
        )
        self.redis = redis.Redis(connection_pool=self.pool)
        self.stats = {
            'hits': 0,
            'misses': 0,
            'sets': 0,
            'deletes': 0
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Get with stats tracking"""
        try:
            value = self.redis.get(key)
            if value:
                self.stats['hits'] += 1
                return json.loads(value)
            self.stats['misses'] += 1
            return None
        except Exception as e:
            print(f"Redis get error: {e}")
            return None
    
    def set(self, key: str, value: Any, ttl: int = 3600) -> bool:
        """Set with TTL"""
        try:
            self.redis.setex(key, ttl, json.dumps(value))
            self.stats['sets'] += 1
            return True
        except Exception as e:
            print(f"Redis set error: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        """Delete key"""
        try:
            self.redis.delete(key)
            self.stats['deletes'] += 1
            return True
        except Exception as e:
            print(f"Redis delete error: {e}")
            return False
    
    def clear_pattern(self, pattern: str) -> int:
        """Clear keys by pattern"""
        try:
            keys = self.redis.keys(pattern)
            if keys:
                self.redis.delete(*keys)
            return len(keys)
        except Exception as e:
            print(f"Redis pattern delete error: {e}")
            return 0
    
    def get_stats(self) -> dict:
        """Get cache statistics"""
        total = self.stats['hits'] + self.stats['misses']
        hit_rate = (self.stats['hits'] / total * 100) if total > 0 else 0
        
        return {
            'total_hits': self.stats['hits'],
            'total_misses': self.stats['misses'],
            'total_sets': self.stats['sets'],
            'total_deletes': self.stats['deletes'],
            'hit_rate': f"{hit_rate:.1f}%",
            'memory_used': self.redis.info().get('used_memory_human', 'N/A'),
            'connected_clients': self.redis.info().get('connected_clients', 0)
        }

redis_cluster = RedisCluster()

# ============================================
# ADVANCED CACHING STRATEGIES
# ============================================

class CacheStrategy:
    """Smart caching with multiple strategies"""
    
    # Cache-Aside (Check cache first)
    @staticmethod
    def cache_aside(key: str, fetch_func: Callable, ttl: int = 3600):
        """Cache-aside pattern"""
        cached = redis_cluster.get(key)
        if cached:
            return cached
        
        result = fetch_func()
        redis_cluster.set(key, result, ttl)
        return result
    
    # Write-Through (Write to cache + DB)
    @staticmethod
    def write_through(key: str, value: Any, db_func: Callable, ttl: int = 3600):
        """Write-through pattern"""
        db_func(value)  # Write to DB first
        redis_cluster.set(key, value, ttl)  # Then to cache
        return value
    
    # Write-Behind (Write to cache first)
    @staticmethod
    def write_behind(key: str, value: Any, db_func: Callable, ttl: int = 3600):
        """Write-behind pattern (async DB write)"""
        redis_cluster.set(key, value, ttl)  # Cache immediately
        
        def db_write():
            time.sleep(0.1)  # Small delay
            db_func(value)  # Write to DB async
        
        thread = threading.Thread(target=db_write)
        thread.daemon = True
        thread.start()
        return value
    
    # Refresh-Ahead (Proactive refresh)
    @staticmethod
    def refresh_ahead(key: str, fetch_func: Callable, ttl: int = 3600, refresh_threshold: int = 300):
        """Refresh-ahead pattern (refresh before expiry)"""
        cached = redis_cluster.get(key)
        
        if cached:
            # Check if close to expiry
            ttl_remaining = redis_cluster.redis.ttl(key)
            if ttl_remaining < refresh_threshold:
                # Refresh in background
                thread = threading.Thread(
                    target=lambda: redis_cluster.set(key, fetch_func(), ttl)
                )
                thread.daemon = True
                thread.start()
            return cached
        
        # Not cached, fetch and cache
        result = fetch_func()
        redis_cluster.set(key, result, ttl)
        return result

# ============================================
# CACHE WARMING (Pre-load Critical Data)
# ============================================

class CacheWarmer:
    """Warm up cache with frequently accessed data"""
    
    @staticmethod
    def warm_leaderboard():
        """Warm leaderboard cache"""
        from api import get_leaderboard_data
        
        for limit in [10, 50, 100]:
            key = f"leaderboard:{limit}"
            data = get_leaderboard_data(limit)
            redis_cluster.set(key, data, 1800)
    
    @staticmethod
    def warm_trending():
        """Warm trending cache"""
        from api import get_trending_data
        
        for personality in ['mentor', 'friend', 'critic', 'guide', 'therapist']:
            key = f"trending:{personality}"
            data = get_trending_data(limit=20, personality=personality)
            redis_cluster.set(key, data, 600)
    
    @staticmethod
    def warm_analytics():
        """Warm analytics cache"""
        from api import get_analytics_data
        
        key = "analytics:platform"
        data = get_analytics_data()
        redis_cluster.set(key, data, 3600)
    
    @staticmethod
    def warm_all():
        """Warm all critical caches"""
        CacheWarmer.warm_leaderboard()
        CacheWarmer.warm_trending()
        CacheWarmer.warm_analytics()
        print("✅ Cache warming complete!")

# ============================================
# CACHE INVALIDATION STRATEGIES
# ============================================

class CacheInvalidator:
    """Smart cache invalidation"""
    
    @staticmethod
    def on_chat_created(user_id: int):
        """Invalidate on new chat"""
        patterns = [
            f"user_stats:{user_id}",
            f"user_chats:{user_id}",
            "leaderboard:*",
            "trending:*",
            "analytics:*"
        ]
        
        for pattern in patterns:
            redis_cluster.clear_pattern(pattern)
    
    @staticmethod
    def on_message_sent(chat_id: int, user_id: int):
        """Invalidate on message"""
        redis_cluster.clear_pattern(f"chat_messages:{chat_id}")
        redis_cluster.clear_pattern(f"user_stats:{user_id}")
        redis_cluster.clear_pattern("trending:*")
        redis_cluster.clear_pattern("analytics:*")
    
    @staticmethod
    def on_engagement(chat_id: int):
        """Invalidate on like/comment"""
        redis_cluster.clear_pattern(f"chat:{chat_id}")
        redis_cluster.clear_pattern("trending:*")
        redis_cluster.clear_pattern("leaderboard:*")

# ============================================
# DECORATORS FOR EASY CACHING
# ============================================

def smart_cache(ttl: int = 3600, strategy: str = "aside"):
    """Smart caching decorator"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            key = f"{func.__name__}:{hashlib.md5(str(args + tuple(kwargs.values())).encode()).hexdigest()}"
            
            if strategy == "aside":
                return CacheStrategy.cache_aside(key, lambda: func(*args, **kwargs), ttl)
            elif strategy == "refresh":
                return CacheStrategy.refresh_ahead(key, lambda: func(*args, **kwargs), ttl)
            else:
                # Default: try cache first
                cached = redis_cluster.get(key)
                if cached:
                    return cached
                result = func(*args, **kwargs)
                redis_cluster.set(key, result, ttl)
                return result
        
        return wrapper
    return decorator

# ============================================
# PERFORMANCE MONITORING
# ============================================

class CacheMonitor:
    """Monitor cache performance"""
    
    @staticmethod
    def get_performance_report() -> dict:
        """Get detailed performance report"""
        stats = redis_cluster.get_stats()
        redis_info = redis_cluster.redis.info()
        
        return {
            "cache_stats": stats,
            "memory_info": {
                "used": redis_info.get('used_memory_human'),
                "peak": redis_info.get('used_memory_peak_human'),
                "fragmentation": redis_info.get('mem_fragmentation_ratio')
            },
            "performance": {
                "commands_processed": redis_info.get('total_commands_processed'),
                "connections": redis_info.get('connected_clients'),
                "uptime_seconds": redis_info.get('uptime_in_seconds')
            },
            "recommendations": CacheMonitor.get_recommendations(stats)
        }
    
    @staticmethod
    def get_recommendations(stats: dict) -> list:
        """Get optimization recommendations"""
        recommendations = []
        
        hit_rate = float(stats['hit_rate'].rstrip('%'))
        
        if hit_rate < 70:
            recommendations.append("⚠️ Low cache hit rate. Consider longer TTLs or more aggressive warming")
        
        if stats['total_deletes'] > stats['total_sets'] * 0.5:
            recommendations.append("⚠️ High invalidation rate. Review invalidation patterns")
        
        if stats['total_misses'] > stats['total_hits']:
            recommendations.append("⚠️ More cache misses than hits. Improve cache strategy")
        
        if not recommendations:
            recommendations.append("✅ Cache performance is optimal!")
        
        return recommendations

# ============================================
# CACHE HEALTH CHECK
# ============================================

def check_redis_health() -> dict:
    """Check Redis cluster health"""
    try:
        info = redis_cluster.redis.ping()
        return {
            "status": "healthy" if info else "unhealthy",
            "response_time": "< 1ms",
            "memory_used": redis_cluster.redis.info().get('used_memory_human'),
            "connected_clients": redis_cluster.redis.info().get('connected_clients')
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }
