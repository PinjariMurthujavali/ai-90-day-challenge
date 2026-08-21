"""
DAY 30: Rate Limiting & Throttling
=====================================
- Token Bucket algorithm (smooth rate limiting)
- Sliding Window Log (precise per-user limiting)
- Per-user + per-IP throttling
- Decorator for easy endpoint protection
"""

import time
import functools
from collections import defaultdict, deque
from threading import Lock


# ---------------- TOKEN BUCKET ----------------

class TokenBucket:
    """Classic token bucket: refills at a steady rate, allows short bursts."""

    def __init__(self, capacity=10, refill_rate=1):
        """
        capacity: max tokens (burst size)
        refill_rate: tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()
        self.lock = Lock()

    def _refill(self):
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def allow(self, cost=1):
        with self.lock:
            self._refill()
            if self.tokens >= cost:
                self.tokens -= cost
                return True
            return False


# ---------------- SLIDING WINDOW LOG ----------------

class SlidingWindowLimiter:
    """Precise limiter: max N requests per window_seconds, tracked with timestamps."""

    def __init__(self, max_requests=5, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)
        self.lock = Lock()

    def allow(self, key):
        now = time.time()
        with self.lock:
            q = self.requests[key]
            while q and q[0] <= now - self.window_seconds:
                q.popleft()
            if len(q) < self.max_requests:
                q.append(now)
                return True
            return False

    def retry_after(self, key):
        q = self.requests[key]
        if not q:
            return 0
        return max(0, round(self.window_seconds - (time.time() - q[0]), 1))


# ---------------- RATE LIMIT MANAGER (per-user + per-IP) ----------------

class RateLimitManager:
    def __init__(self, user_limit=20, user_window=60, ip_limit=100, ip_window=60):
        self.user_limiter = SlidingWindowLimiter(user_limit, user_window)
        self.ip_limiter = SlidingWindowLimiter(ip_limit, ip_window)

    def check(self, user_id=None, ip=None):
        if ip and not self.ip_limiter.allow(f"ip:{ip}"):
            return False, "IP rate limit exceeded", self.ip_limiter.retry_after(f"ip:{ip}")
        if user_id and not self.user_limiter.allow(f"user:{user_id}"):
            return False, "User rate limit exceeded", self.user_limiter.retry_after(f"user:{user_id}")
        return True, "OK", 0


manager = RateLimitManager(user_limit=20, user_window=60, ip_limit=100, ip_window=60)


# ---------------- DECORATOR FOR EASY USE ----------------

def rate_limit(user_id_arg="user_id", ip_arg="ip"):
    """Decorator to protect any function/endpoint with rate limiting."""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            uid = kwargs.get(user_id_arg)
            ip = kwargs.get(ip_arg)
            allowed, reason, retry_after = manager.check(user_id=uid, ip=ip)
            if not allowed:
                return {
                    "error": "Too Many Requests",
                    "reason": reason,
                    "retry_after_seconds": retry_after,
                    "status_code": 429,
                }
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ---------------- DEMO ----------------

@rate_limit()
def send_chat_message(user_id=None, ip=None, message=""):
    return {"status": "sent", "message": message}


def demo():
    print("=" * 50)
    print("DAY 30: RATE LIMITING & THROTTLING DEMO")
    print("=" * 50)

    print("\n🪣 Token Bucket test (capacity=5, refill=1/sec)")
    bucket = TokenBucket(capacity=5, refill_rate=1)
    for i in range(7):
        allowed = bucket.allow()
        print(f"   Request {i+1}: {'✅ allowed' if allowed else '❌ blocked'}")

    print("\n🪟 Sliding Window test (max 3 requests / 5 sec, user=murthu)")
    limiter = SlidingWindowLimiter(max_requests=3, window_seconds=5)
    for i in range(5):
        allowed = limiter.allow("murthu")
        retry = limiter.retry_after("murthu") if not allowed else 0
        print(f"   Request {i+1}: {'✅ allowed' if allowed else f'❌ blocked (retry in {retry}s)'}")

    print("\n🧑 Per-user + per-IP decorator test (limit=20/min user, 100/min IP)")
    for i in range(3):
        result = send_chat_message(user_id="murthu", ip="192.168.1.1", message=f"hi {i}")
        print(f"   Message {i+1}: {result}")


if __name__ == "__main__":
    demo()
