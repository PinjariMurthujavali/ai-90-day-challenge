# ============================================
# Day 13: Flask App with GraphQL + Redis Cache
# ============================================

from flask import Flask, jsonify, request
from flask_cors import CORS
from graphql_schema import schema
from cache_layer import cache_manager, CacheInvalidator, get_cache_status, warm_cache
import sqlite3
from datetime import datetime
from functools import wraps

app = Flask(__name__)
CORS(app)

DB_FILE = "chatbot.db"

# ============================================
# GRAPHQL ENDPOINT
# ============================================

@app.route('/graphql', methods=['GET', 'POST'])
def graphql_view():
    """GraphQL endpoint"""
    from graphene import Schema
    from graphql import graphql_sync
    from graphql_schema import Query
    
    query_string = request.args.get('query') or (request.json.get('query') if request.json else '')
    
    result = graphql_sync(
        schema.graphql_schema,
        query_string
    )
    
    if result.errors:
        return jsonify({"errors": [str(e) for e in result.errors]}), 400
    
    return jsonify({"data": result.data}), 200

# ============================================
# REST API ENDPOINTS (CACHED)
# ============================================

def cached_endpoint(ttl=3600):
    """Decorator for caching REST endpoints"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = f"endpoint:{request.path}:{request.query_string.decode()}"
            
            # Try cache
            cached = cache_manager.get(cache_key)
            if cached is not None:
                return jsonify(cached), 200
            
            # Execute
            result = func(*args, **kwargs)
            
            if isinstance(result, tuple):
                data, status_code = result
            else:
                data, status_code = result, 200
            
            # Cache successful responses
            if status_code == 200 and isinstance(data, dict):
                cache_manager.set(cache_key, data, ttl)
            
            return jsonify(data), status_code
        return wrapper
    return decorator

@app.route('/api/v1/leaderboard', methods=['GET'])
@cached_endpoint(ttl=1800)
def get_leaderboard():
    """Get cached leaderboard"""
    limit = request.args.get('limit', 50, type=int)
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT u.id, u.username, COUNT(c.id) as chats,
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
    
    leaderboard = [
        {
            "rank": i+1,
            "user_id": r[0],
            "username": r[1],
            "chats": r[2] or 0,
            "messages": r[3] or 0,
            "score": float(r[4] or 0)
        }
        for i, r in enumerate(results)
    ]
    
    return {"leaderboard": leaderboard}, 200

@app.route('/api/v1/trending', methods=['GET'])
@cached_endpoint(ttl=600)
def get_trending():
    """Get cached trending chats"""
    limit = request.args.get('limit', 20, type=int)
    
    conn = sqlite3.connect(DB_FILE)
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
    
    trending = [
        {
            "chat_id": r[0],
            "title": r[1],
            "personality": r[2],
            "author": r[3],
            "activity_score": float(r[4] or 0),
            "trending_position": i+1
        }
        for i, r in enumerate(results)
    ]
    
    return {"trending": trending}, 200

@app.route('/api/v1/analytics', methods=['GET'])
@cached_endpoint(ttl=3600)
def get_analytics():
    """Get cached analytics"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM chats')
    total_chats = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM messages')
    total_messages = cursor.fetchone()[0]
    
    cursor.execute('''
        SELECT personality, COUNT(*) FROM chats GROUP BY personality
    ''')
    personality_stats = dict(cursor.fetchall())
    
    conn.close()
    
    return {
        "total_users": total_users,
        "total_chats": total_chats,
        "total_messages": total_messages,
        "personality_breakdown": personality_stats
    }, 200

# ============================================
# CACHE MANAGEMENT ENDPOINTS
# ============================================

@app.route('/api/v1/cache/status', methods=['GET'])
def cache_status():
    """Get cache status"""
    return jsonify(get_cache_status()), 200

@app.route('/api/v1/cache/warm', methods=['POST'])
def cache_warm():
    """Warm up cache"""
    try:
        warm_cache()
        return jsonify({"success": True, "message": "Cache warmed up"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/v1/cache/clear', methods=['POST'])
def cache_clear():
    """Clear all cache"""
    data = request.get_json()
    pattern = data.get('pattern', '*')
    
    cleared = cache_manager.clear_pattern(pattern)
    
    return jsonify({
        "success": True,
        "message": f"Cleared {cleared} cache keys",
        "pattern": pattern
    }), 200

@app.route('/api/v1/cache/invalidate/<path>', methods=['POST'])
def cache_invalidate(path):
    """Invalidate specific cache"""
    cache_manager.delete(path)
    return jsonify({"success": True, "message": f"Invalidated {path}"}), 200

# ============================================
# SEARCH WITH FULL-TEXT (CACHED)
# ============================================

@app.route('/api/v1/search', methods=['GET'])
@cached_endpoint(ttl=300)
def search():
    """Search with caching"""
    query = request.args.get('q', '')
    
    if len(query) < 2:
        return {"error": "Query too short"}, 400
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    search_query = f"%{query}%"
    
    cursor.execute('''
        SELECT DISTINCT c.id, c.title, u.username,
               COUNT(m.id) as message_count
        FROM chats c
        LEFT JOIN users u ON c.user_id = u.id
        LEFT JOIN messages m ON c.id = m.chat_id
        WHERE LOWER(c.title) LIKE LOWER(?) 
           OR LOWER(m.content) LIKE LOWER(?)
        GROUP BY c.id
        LIMIT 50
    ''', (search_query, search_query))
    
    results = cursor.fetchall()
    conn.close()
    
    data = [
        {
            "id": r[0],
            "title": r[1],
            "author": r[2],
            "messages": r[3] or 0
        }
        for r in results
    ]
    
    return {"results": data, "count": len(data)}, 200

# ============================================
# REAL-TIME STATS (MINIMAL CACHE)
# ============================================

@app.route('/api/v1/stats/realtime', methods=['GET'])
def realtime_stats():
    """Real-time statistics (5 sec cache)"""
    cache_key = "stats:realtime"
    
    cached = cache_manager.get(cache_key)
    if cached:
        return jsonify(cached), 200
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            COUNT(DISTINCT u.id) as active_users,
            COUNT(DISTINCT c.id) as active_chats,
            COUNT(m.id) as messages_last_hour
        FROM users u
        LEFT JOIN chats c ON u.id = c.user_id
        LEFT JOIN messages m ON c.id = m.chat_id 
            AND m.timestamp > datetime('now', '-1 hour')
    ''')
    
    result = cursor.fetchone()
    conn.close()
    
    data = {
        "active_users": result[0],
        "active_chats": result[1],
        "messages_last_hour": result[2],
        "timestamp": datetime.now().isoformat()
    }
    
    cache_manager.set(cache_key, data, 5)
    
    return jsonify(data), 200

# ============================================
# HEALTH CHECK
# ============================================

@app.route('/api/v1/health', methods=['GET'])
def health():
    """Health check with cache status"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cache": get_cache_status(),
        "graphql": "/graphql",
        "api_version": "1.3.0"
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

# ============================================
# STARTUP
# ============================================

if __name__ == '__main__':
    print("🚀 Day 13: GraphQL + Redis Cache Starting...")
    print("✅ GraphQL endpoint: http://localhost:5000/graphql")
    print("✅ REST API: http://localhost:5000/api/v1/...")
    print("✅ Cache Status: http://localhost:5000/api/v1/cache/status")
    
    app.run(debug=True, port=5000)
