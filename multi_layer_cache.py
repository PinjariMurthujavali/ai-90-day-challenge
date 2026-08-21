"""
DAY 32: Multi-Layer Caching Strategies
==========================================
- L1: In-memory cache (fastest, per-process)
- L2: Simulated Redis-style cache (shared, slower than L1)
- Cache-aside pattern with automatic promotion (L2 hit -> populate L1)
- TTL expiry + LRU eviction
- Cache stats (hit rate per layer)
"""

import time
import functools
from collections import OrderedDict
from threading import Lock


# ---------------- L1: IN-MEMORY LRU CACHE ----------------

class L1Cache:
    """Fastest layer - in-process memory, small capacity, LRU eviction."""

    def __init__(self, capacity=100, default_ttl=30):
        self.capacity = capacity
        self.default_ttl = default_ttl
        self.store = OrderedDict()  # key -> (value, expiry_time)
        self.lock = Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        with self.lock:
            if key not in self.store:
                self.misses += 1
                return None
            value, expiry = self.store[key]
            if time.time() > expiry:
                del self.store[key]
                self.misses += 1
                return None
            self.store.move_to_end(key)
            self.hits += 1
            return value

    def set(self, key, value, ttl=None):
        with self.lock:
            ttl = ttl or self.default_ttl
            if key in self.store:
                self.store.move_to_end(key)
            self.store[key] = (value, time.time() + ttl)
            if len(self.store) > self.capacity:
                self.store.popitem(last=False)  # evict least recently used

    def invalidate(self, key):
        with self.lock:
            self.store.pop(key, None)


# ---------------- L2: SIMULATED REDIS (SHARED, SLOWER, BIGGER) ----------------

class L2Cache:
    """Simulates a shared cache layer (like Redis) - bigger capacity, simulated network latency."""

    def __init__(self, capacity=1000, default_ttl=300, simulated_latency_ms=5):
        self.capacity = capacity
        self.default_ttl = default_ttl
        self.simulated_latency = simulated_latency_ms / 1000
        self.store = OrderedDict()
        self.lock = Lock()
        self.hits = 0
        self.misses = 0

    def get(self, key):
        time.sleep(self.simulated_latency)  # simulate network round-trip
        with self.lock:
            if key not in self.store:
                self.misses += 1
                return None
            value, expiry = self.store[key]
            if time.time() > expiry:
                del self.store[key]
                self.misses += 1
                return None
            self.hits += 1
            return value

    def set(self, key, value, ttl=None):
        time.sleep(self.simulated_latency)
        with self.lock:
            ttl = ttl or self.default_ttl
            self.store[key] = (value, time.time() + ttl)
            if len(self.store) > self.capacity:
                self.store.popitem(last=False)

    def invalidate(self, key):
        with self.lock:
            self.store.pop(key, None)


# ---------------- MULTI-LAYER CACHE MANAGER ----------------

class MultiLayerCache:
    """
    Cache-aside pattern across L1 (memory) -> L2 (shared) -> source (DB/API).
    On L2 hit, automatically promotes the value into L1 for next time.
    """

    def __init__(self, l1=None, l2=None):
        self.l1 = l1 or L1Cache()
        self.l2 = l2 or L2Cache()

    def get_or_load(self, key, loader_func, ttl_l1=30, ttl_l2=300):
        # L1 first
        value = self.l1.get(key)
        if value is not None:
            return value, "L1_HIT"

        # L2 next
        value = self.l2.get(key)
        if value is not None:
            self.l1.set(key, value, ttl=ttl_l1)  # promote to L1
            return value, "L2_HIT"

        # Cache miss everywhere -> load from source
        value = loader_func()
        self.l1.set(key, value, ttl=ttl_l1)
        self.l2.set(key, value, ttl=ttl_l2)
        return value, "MISS_LOADED_FROM_SOURCE"

    def invalidate(self, key):
        self.l1.invalidate(key)
        self.l2.invalidate(key)

    def stats(self):
        return {
            "L1": {"hits": self.l1.hits, "misses": self.l1.misses,
                   "hit_rate": self._rate(self.l1.hits, self.l1.misses)},
            "L2": {"hits": self.l2.hits, "misses": self.l2.misses,
                   "hit_rate": self._rate(self.l2.hits, self.l2.misses)},
        }

    @staticmethod
    def _rate(hits, misses):
        total = hits + misses
        return f"{(hits/total*100):.1f}%" if total else "0%"


cache = MultiLayerCache()


# ---------------- DECORATOR FOR EASY USE ----------------

def cached(ttl_l1=30, ttl_l2=300):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{args}:{sorted(kwargs.items())}"
            value, source = cache.get_or_load(
                key, lambda: func(*args, **kwargs), ttl_l1=ttl_l1, ttl_l2=ttl_l2
            )
            return value, source
        return wrapper
    return decorator


# ---------------- DEMO: simulate an expensive DB call ----------------

@cached(ttl_l1=10, ttl_l2=60)
def get_chat_history(user_id):
    time.sleep(0.05)  # simulate slow DB query
    return {"user_id": user_id, "chats": ["Project ideas", "Trip planning"]}


def demo():
    print("=" * 50)
    print("DAY 32: MULTI-LAYER CACHING DEMO")
    print("=" * 50)

    print("\n📞 Calling get_chat_history('murthu') 4 times:")
    for i in range(4):
        start = time.perf_counter()
        result, source = get_chat_history(user_id="murthu")
        elapsed_ms = (time.perf_counter() - start) * 1000
        print(f"   Call {i+1}: {source} ({elapsed_ms:.2f} ms)")

    print("\n🗑️ Invalidating L1 manually to force L2 hit:")
    key = "get_chat_history:('murthu',):[]" if False else None
    # simulate invalidation flow directly via cache manager
    cache.l1.store.clear()
    result, source = get_chat_history(user_id="murthu")
    print(f"   After L1 clear: {source}")

    print("\n📊 Cache stats:")
    for layer, s in cache.stats().items():
        print(f"   {layer}: {s}")


if __name__ == "__main__":
    demo()
