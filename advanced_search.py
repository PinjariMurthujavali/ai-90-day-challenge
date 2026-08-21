"""
DAY 29: Elasticsearch-style Advanced Search
=============================================
- Inverted index (built in-memory from SQLite data)
- Relevance ranking (TF-IDF scoring)
- Fuzzy matching (typo tolerance via Levenshtein distance)
- Multi-field search (title + message content)
"""

import sqlite3
import math
import re
from collections import defaultdict, Counter

DB_PATH = "chatbot.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def tokenize(text):
    return re.findall(r"[a-z0-9]+", (text or "").lower())


# ---------------- INVERTED INDEX ----------------

class SearchIndex:
    """In-memory inverted index mimicking Elasticsearch core concepts."""

    def __init__(self):
        self.index = defaultdict(set)       # word -> set of doc_ids
        self.doc_store = {}                 # doc_id -> {title, content, type}
        self.doc_freq = defaultdict(int)    # word -> number of docs containing it
        self.total_docs = 0

    def add_document(self, doc_id, title="", content="", doc_type="chat"):
        text = f"{title} {content}"
        words = tokenize(text)
        self.doc_store[doc_id] = {"title": title, "content": content, "type": doc_type}
        self.total_docs += 1

        seen = set()
        for word in words:
            self.index[word].add(doc_id)
            if word not in seen:
                self.doc_freq[word] += 1
                seen.add(word)

    def build_from_db(self):
        with get_connection() as conn:
            chats = conn.execute("SELECT id, title FROM chats").fetchall()
            for c in chats:
                self.add_document(f"chat_{c['id']}", title=c["title"], doc_type="chat")

            messages = conn.execute("SELECT id, chat_id, content FROM messages").fetchall()
            for m in messages:
                self.add_document(f"msg_{m['id']}", content=m["content"], doc_type="message")


# ---------------- FUZZY MATCHING ----------------

def levenshtein(a, b):
    if len(a) < len(b):
        return levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev_row = range(len(b) + 1)
    for i, ca in enumerate(a):
        curr_row = [i + 1]
        for j, cb in enumerate(b):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (ca != cb)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def fuzzy_match_words(query_word, index, max_distance=2):
    """Find indexed words within edit-distance of the query word (typo tolerance)."""
    matches = []
    for word in index.index.keys():
        if abs(len(word) - len(query_word)) > max_distance:
            continue
        if levenshtein(query_word, word) <= max_distance:
            matches.append(word)
    return matches


# ---------------- SEARCH + RANKING (TF-IDF) ----------------

def search(index: SearchIndex, query, fuzzy=True, top_n=10):
    query_words = tokenize(query)
    if not query_words:
        return []

    scores = defaultdict(float)

    for qword in query_words:
        matched_words = {qword} if qword in index.index else set()

        if fuzzy:
            matched_words |= set(fuzzy_match_words(qword, index))

        for word in matched_words:
            doc_ids = index.index.get(word, set())
            df = index.doc_freq.get(word, 1)
            idf = math.log((index.total_docs + 1) / (df + 1)) + 1
            weight = idf if word == qword else idf * 0.5  # fuzzy matches score lower

            for doc_id in doc_ids:
                text = f"{index.doc_store[doc_id]['title']} {index.doc_store[doc_id]['content']}"
                tf = tokenize(text).count(word)
                scores[doc_id] += tf * weight

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
    results = []
    for doc_id, score in ranked:
        doc = index.doc_store[doc_id]
        results.append({
            "id": doc_id,
            "type": doc["type"],
            "title": doc["title"],
            "snippet": (doc["content"] or doc["title"] or "")[:100],
            "score": round(score, 3),
        })
    return results


# ---------------- DEMO ----------------

def demo():
    print("=" * 50)
    print("DAY 29: ADVANCED SEARCH ENGINE DEMO")
    print("=" * 50)

    idx = SearchIndex()
    idx.build_from_db()
    print(f"\n📚 Indexed {idx.total_docs} documents, {len(idx.index)} unique terms")

    test_queries = ["chat", "hello", "chatbo"]  # last one intentionally typo'd
    for q in test_queries:
        print(f"\n🔍 Search: '{q}'")
        results = search(idx, q, fuzzy=True, top_n=5)
        if not results:
            print("   No results")
        for r in results:
            print(f"   [{r['score']}] ({r['type']}) {r['title'] or r['snippet']}")


if __name__ == "__main__":
    demo()
