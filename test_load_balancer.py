"""Tests for Day 42: Service Discovery & Load Balancing."""

import pytest
from load_balancer import LoadBalancedRegistry


@pytest.fixture
def registry():
    r = LoadBalancedRegistry()
    r.register("svc", "http://a", weight=1)
    r.register("svc", "http://b", weight=1)
    r.register("svc", "http://c", weight=1)
    return r


def test_round_robin_cycles_through_all_instances(registry):
    picks = [registry.get_instance("svc", strategy="round_robin") for _ in range(6)]
    assert picks == ["http://a", "http://b", "http://c", "http://a", "http://b", "http://c"]


def test_no_healthy_instances_returns_none():
    r = LoadBalancedRegistry()
    assert r.get_instance("ghost-service") is None


def test_unhealthy_instance_excluded_from_selection(registry):
    registry.mark_unhealthy("svc", "http://b")
    picks = {registry.get_instance("svc", strategy="round_robin") for _ in range(10)}
    assert "http://b" not in picks
    assert picks == {"http://a", "http://c"}


def test_least_connections_picks_idle_instance(registry):
    registry.start_call("svc", "http://a")
    registry.start_call("svc", "http://a")
    registry.start_call("svc", "http://b")
    chosen = registry.get_instance("svc", strategy="least_connections")
    assert chosen == "http://c"  # 0 active connections


def test_weighted_favors_higher_weight_instance():
    r = LoadBalancedRegistry()
    r.register("svc", "http://light", weight=1)
    r.register("svc", "http://heavy", weight=9)

    from collections import Counter
    picks = Counter(r.get_instance("svc", strategy="weighted") for _ in range(1000))
    assert picks["http://heavy"] > picks["http://light"] * 3  # roughly 9:1, allow slack


def test_deregister_removes_instance(registry):
    registry.deregister("svc", "http://a")
    picks = {registry.get_instance("svc", strategy="round_robin") for _ in range(10)}
    assert "http://a" not in picks


def test_call_with_tracking_context_manager(registry):
    with registry.call_with_tracking("svc", strategy="round_robin") as url:
        status = registry.status("svc")
        active = next(s for s in status if s["url"] == url)
        assert active["active_connections"] == 1

    status_after = registry.status("svc")
    active_after = next(s for s in status_after if s["url"] == url)
    assert active_after["active_connections"] == 0


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
