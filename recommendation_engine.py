"""
DAY 28: Machine Learning Recommendations
==========================================
- Content-based chat/personality recommendations
- Collaborative filtering (users who liked similar chats)
- Trending topics engine
"""

import sqlite3
import math
from collections import Counter, defaultdict

DB_PATH = "chatbot.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------- CONTENT-BASED RECOMMENDATIONS ----------------

def recommend_personalities_for_user(user_id, top_n=3):
    """Recommend chat personalities based on user's past chat history."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT personality FROM chats WHERE user_id = ?", (user_id,)
        ).fetchall()

    if not rows:
        return _fallback_popular_personalities(top_n)

    counts = Counter(r["personality"] for r in rows if r["personality"])
    used = set(counts.keys())

    with get_connection() as conn:
        all_personalities = conn.execute(
            "SELECT personality, COUNT(*) as cnt FROM chats WHERE personality IS NOT NULL GROUP BY personality ORDER BY cnt DESC"
        ).fetchall()

    recommendations = [
        row["personality"] for row in all_personalities
        if row["personality"] not in used
    ][:top_n]

    if len(recommendations) < top_n:
        recommendations += [p for p in counts.keys() if p not in recommendations][:top_n - len(recommendations)]

    return recommendations


def _fallback_popular_personalities(top_n=3):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT personality, COUNT(*) as cnt FROM chats WHERE personality IS NOT NULL GROUP BY personality ORDER BY cnt DESC LIMIT ?",
            (top_n,)
        ).fetchall()
    return [r["personality"] for r in rows]


# ---------------- COLLABORATIVE FILTERING ----------------

def recommend_chats_for_user(user_id, top_n=5):
    """
    'Users who liked what you liked, also liked...' style recommendation.
    Simple user-based collaborative filtering using Jaccard similarity on likes.
    """
    with get_connection() as conn:
        my_likes = {r["chat_id"] for r in conn.execute(
            "SELECT chat_id FROM likes WHERE user_id = ?", (user_id,)
        ).fetchall()}

        if not my_likes:
            return _fallback_trending_chats(top_n)

        all_likes = conn.execute("SELECT user_id, chat_id FROM likes").fetchall()

    user_likes_map = defaultdict(set)
    for row in all_likes:
        user_likes_map[row["user_id"]].add(row["chat_id"])

    similarities = []
    for other_user, other_likes in user_likes_map.items():
        if other_user == user_id:
            continue
        intersection = len(my_likes & other_likes)
        if intersection == 0:
            continue
        union = len(my_likes | other_likes)
        jaccard = intersection / union
        similarities.append((other_user, jaccard, other_likes))

    similarities.sort(key=lambda x: x[1], reverse=True)

    scores = defaultdict(float)
    for other_user, sim, other_likes in similarities[:20]:
        for chat_id in other_likes - my_likes:
            scores[chat_id] += sim

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [chat_id for chat_id, score in ranked] or _fallback_trending_chats(top_n)


def _fallback_trending_chats(top_n=5):
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT chat_id, COUNT(*) as cnt FROM likes
               GROUP BY chat_id ORDER BY cnt DESC LIMIT ?""",
            (top_n,)
        ).fetchall()
    return [r["chat_id"] for r in rows]


# ---------------- TRENDING TOPICS (TF-IDF style scoring) ----------------

def trending_topics(top_n=10):
    """Extract trending keywords from recent chat titles using simple TF-IDF."""
    with get_connection() as conn:
        titles = [r["title"] for r in conn.execute(
            "SELECT title FROM chats WHERE title IS NOT NULL ORDER BY created_at DESC LIMIT 200"
        ).fetchall()]

    if not titles:
        return []

    stopwords = {"the", "a", "an", "and", "or", "for", "of", "to", "in", "on", "is", "with", "my"}
    doc_word_sets = []
    word_freq = Counter()

    for title in titles:
        words = [w.lower() for w in title.split() if w.lower() not in stopwords and len(w) > 2]
        word_freq.update(words)
        doc_word_sets.append(set(words))

    n_docs = len(titles)
    tfidf_scores = {}
    for word, tf in word_freq.items():
        df = sum(1 for doc in doc_word_sets if word in doc)
        idf = math.log((n_docs + 1) / (df + 1)) + 1
        tfidf_scores[word] = tf * idf

    ranked = sorted(tfidf_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    return [{"topic": word, "score": round(score, 2)} for word, score in ranked]


# ---------------- DEMO ----------------

def demo():
    print("=" * 50)
    print("DAY 28: ML RECOMMENDATIONS DEMO")
    print("=" * 50)

    with get_connection() as conn:
        sample_user = conn.execute("SELECT id FROM users LIMIT 1").fetchone()

    if sample_user:
        uid = sample_user["id"]
        print(f"\n👤 Recommendations for user {uid}")
        print("🎭 Personalities:", recommend_personalities_for_user(uid))
        print("💬 Chats (collaborative filtering):", recommend_chats_for_user(uid))
    else:
        print("No users found in DB.")

    print("\n🔥 Trending topics:")
    for t in trending_topics(5):
        print(f"   {t['topic']} (score: {t['score']})")


if __name__ == "__main__":
    demo()
