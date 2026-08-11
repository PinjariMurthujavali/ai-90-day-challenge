"""
DAY 44: Inter-service Communication
=======================================
Day 43's gateway could DECIDE which service/instance should handle a
request, but never actually called it — it just returned "this is where
it would go." Day 44 closes that gap: real HTTP calls from one service to
another, made resilient the way production systems actually need:

  - Retries with exponential backoff  — transient failures (a dropped
    connection, a momentary timeout) shouldn't fail the whole request
  - Circuit breaker                   — if a service is DOWN, stop hammering
    it with retries after N consecutive failures; fail fast instead, and
    periodically test if it's recovered
  - Timeouts                          — a slow service should never be
    allowed to hang the caller forever
  - A simple in-memory event bus      — for the async side of inter-service
    communication: one service publishes an event ("chat_created"),
    other services subscribe without the publisher knowing who's listening

Run tests:
    pytest test_inter_service.py -v
"""

import time
import random
from collections import defaultdict
from enum import Enum


# ============================================
# CIRCUIT BREAKER
# ============================================

class CircuitState(Enum):
    CLOSED = "closed"        # normal operation, calls go through
    OPEN = "open"             # service considered down, calls fail fast
    HALF_OPEN = "half_open"   # testing if the service has recovered


class CircuitBreaker:
    """
    One breaker per downstream service. Trips OPEN after `failure_threshold`
    consecutive failures. Once OPEN, fails every call immediately (no
    network call at all) until `reset_timeout` seconds pass, then allows
    exactly one HALF_OPEN test call through to check recovery.
    """

    def __init__(self, failure_threshold=3, reset_timeout=10):
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at = None

    def allow_request(self):
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.opened_at >= self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow the single probe call through
        return True

    def record_success(self):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at = None

    def record_failure(self):
        self.failure_count += 1
        if self.state == CircuitState.HALF_OPEN or self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = time.time()


class CircuitBreakerRegistry:
    """Holds one breaker per service name so failures in one service can't
    trip the breaker for an unrelated one."""

    def __init__(self, failure_threshold=3, reset_timeout=10):
        self._breakers = {}
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout

    def get(self, service_name):
        if service_name not in self._breakers:
            self._breakers[service_name] = CircuitBreaker(
                self.failure_threshold, self.reset_timeout
            )
        return self._breakers[service_name]


# ============================================
# RESILIENT CALL (retries + backoff + circuit breaker + timeout)
# ============================================

class ServiceUnavailableError(Exception):
    """Raised when the circuit breaker is open — we deliberately did not
    even attempt the network call."""
    pass


class InterServiceClient:
    """
    Wraps calls to other services with the resilience patterns real
    distributed systems rely on. `call_func` is any zero-arg callable that
    performs the actual network call (kept pluggable so this is testable
    without real HTTP — tests inject a fake call_func).
    """

    def __init__(self, max_retries=3, base_backoff=0.1, timeout=2,
                 failure_threshold=3, reset_timeout=10):
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.timeout = timeout
        self.breakers = CircuitBreakerRegistry(failure_threshold, reset_timeout)
        self.call_log = []

    def call(self, service_name, call_func, sleep_func=time.sleep):
        breaker = self.breakers.get(service_name)

        if not breaker.allow_request():
            self.call_log.append({"service": service_name, "result": "circuit_open"})
            raise ServiceUnavailableError(
                f"Circuit breaker OPEN for '{service_name}' — failing fast, not calling."
            )

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                result = call_func()
                breaker.record_success()
                self.call_log.append({
                    "service": service_name, "result": "success", "attempt": attempt
                })
                return result
            except Exception as e:
                last_error = e
                breaker.record_failure()
                self.call_log.append({
                    "service": service_name, "result": "failure",
                    "attempt": attempt, "error": str(e),
                })
                if not breaker.allow_request():
                    # Breaker just tripped from this failure — stop retrying immediately
                    break
                if attempt < self.max_retries:
                    backoff = self.base_backoff * (2 ** (attempt - 1))
                    backoff += random.uniform(0, self.base_backoff)  # jitter
                    sleep_func(backoff)

        raise last_error if last_error else ServiceUnavailableError(service_name)


# ============================================
# EVENT BUS (async inter-service communication)
# ============================================

class EventBus:
    """
    Minimal in-memory pub/sub: services publish events by name, other
    services subscribe without either side knowing about the other
    directly. In production this role is played by Kafka, RabbitMQ, or
    SNS/SQS — same shape, simplified to fit in one file.
    """

    def __init__(self):
        self._subscribers = defaultdict(list)
        self.published_events = []

    def subscribe(self, event_name, handler):
        self._subscribers[event_name].append(handler)

    def publish(self, event_name, payload):
        self.published_events.append({"event": event_name, "payload": payload, "at": time.time()})
        results = []
        for handler in self._subscribers[event_name]:
            try:
                results.append(handler(payload))
            except Exception as e:
                results.append({"error": str(e)})
        return results


# ============================================
# DEMO: chat-service notifying analytics-service of a new chat
# ============================================

def demo():
    client = InterServiceClient(max_retries=3, base_backoff=0.05, failure_threshold=5, reset_timeout=1)
    bus = EventBus()

    # analytics-service subscribes to "chat_created" events
    received = []
    bus.subscribe("chat_created", lambda payload: received.append(payload))

    print("=== Publishing chat_created event ===")
    bus.publish("chat_created", {"chat_id": 42, "user_id": 7, "title": "Demo Chat"})
    print("Received by analytics-service:", received)

    print("\n=== Resilient call: flaky service that fails twice then succeeds ===")
    attempts = {"count": 0}

    def flaky_call():
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise ConnectionError("simulated network blip")
        return {"status": "ok"}

    result = client.call("flaky-service", flaky_call)
    print("Result:", result, "| Call log:", client.call_log)

    print("\n=== Circuit breaker: service that always fails ===")
    def always_fails():
        raise ConnectionError("service is down")

    client2 = InterServiceClient(max_retries=1, failure_threshold=2, reset_timeout=100)
    for i in range(4):
        try:
            client2.call("dead-service", always_fails)
        except ServiceUnavailableError as e:
            print(f"  Call {i+1}: circuit breaker blocked it fast -> {e}")
        except ConnectionError:
            print(f"  Call {i+1}: real network attempt failed")


if __name__ == "__main__":
    demo()
