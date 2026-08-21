"""Tests for Day 44: Inter-service Communication."""

import pytest
from inter_service_client import (
    InterServiceClient, CircuitBreaker, CircuitState,
    EventBus, ServiceUnavailableError,
)


# ---------------- CIRCUIT BREAKER ----------------

def test_circuit_starts_closed():
    cb = CircuitBreaker()
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True


def test_circuit_opens_after_threshold_failures():
    cb = CircuitBreaker(failure_threshold=3)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False


def test_circuit_half_opens_after_reset_timeout():
    cb = CircuitBreaker(failure_threshold=1, reset_timeout=0)
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is True  # reset_timeout=0, elapsed >= 0 immediately
    assert cb.state == CircuitState.HALF_OPEN


def test_success_resets_circuit():
    cb = CircuitBreaker(failure_threshold=2)
    cb.record_failure()
    cb.record_success()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


# ---------------- RETRIES ----------------

def test_call_succeeds_on_first_try():
    client = InterServiceClient()
    result = client.call("svc", lambda: {"ok": True}, sleep_func=lambda s: None)
    assert result == {"ok": True}


def test_call_retries_and_eventually_succeeds():
    client = InterServiceClient(max_retries=3, failure_threshold=5)
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ConnectionError("blip")
        return "recovered"

    result = client.call("svc", flaky, sleep_func=lambda s: None)
    assert result == "recovered"
    assert attempts["n"] == 3


def test_call_raises_after_exhausting_retries():
    client = InterServiceClient(max_retries=2, failure_threshold=10)

    def always_fails():
        raise ConnectionError("nope")

    with pytest.raises(ConnectionError):
        client.call("svc", always_fails, sleep_func=lambda s: None)


def test_backoff_increases_between_retries():
    client = InterServiceClient(max_retries=3, base_backoff=1, failure_threshold=10)
    sleeps = []

    def always_fails():
        raise ConnectionError("nope")

    with pytest.raises(ConnectionError):
        client.call("svc", always_fails, sleep_func=lambda s: sleeps.append(s))

    assert len(sleeps) == 2  # slept between attempt 1->2 and 2->3, not after the last
    assert sleeps[1] > sleeps[0] * 1.5  # exponential-ish growth despite jitter


# ---------------- CIRCUIT BREAKER + CLIENT INTEGRATION ----------------

def test_open_circuit_blocks_calls_without_attempting_network():
    client = InterServiceClient(max_retries=5, failure_threshold=1, reset_timeout=1000)
    call_count = {"n": 0}

    def always_fails():
        call_count["n"] += 1
        raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        client.call("svc", always_fails, sleep_func=lambda s: None)

    calls_after_trip = call_count["n"]

    # Circuit is now OPEN — this call must fail fast with ServiceUnavailableError,
    # and must NOT have incremented call_count (no network attempt at all)
    with pytest.raises(ServiceUnavailableError):
        client.call("svc", always_fails, sleep_func=lambda s: None)

    assert call_count["n"] == calls_after_trip


def test_different_services_have_independent_circuits():
    client = InterServiceClient(max_retries=1, failure_threshold=1, reset_timeout=1000)

    def fails():
        raise ConnectionError("down")

    with pytest.raises(ConnectionError):
        client.call("service-a", fails, sleep_func=lambda s: None)

    # service-b's circuit must still be closed — service-a's failure shouldn't affect it
    result = client.call("service-b", lambda: "fine", sleep_func=lambda s: None)
    assert result == "fine"


# ---------------- EVENT BUS ----------------

def test_publish_with_no_subscribers_does_not_error():
    bus = EventBus()
    results = bus.publish("nobody_listening", {"x": 1})
    assert results == []


def test_subscriber_receives_published_payload():
    bus = EventBus()
    received = []
    bus.subscribe("chat_created", lambda payload: received.append(payload))
    bus.publish("chat_created", {"chat_id": 5})
    assert received == [{"chat_id": 5}]


def test_multiple_subscribers_all_receive_event():
    bus = EventBus()
    calls = []
    bus.subscribe("evt", lambda p: calls.append("handler1"))
    bus.subscribe("evt", lambda p: calls.append("handler2"))
    bus.publish("evt", {})
    assert calls == ["handler1", "handler2"]


def test_failing_subscriber_does_not_break_others():
    bus = EventBus()
    calls = []

    def bad_handler(payload):
        raise RuntimeError("boom")

    def good_handler(payload):
        calls.append("good")

    bus.subscribe("evt", bad_handler)
    bus.subscribe("evt", good_handler)
    bus.publish("evt", {})
    assert "good" in calls


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
