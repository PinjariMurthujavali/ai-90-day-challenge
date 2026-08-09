"""Tests for Day 43: API Gateway Implementation."""

import pytest
from api_gateway import APIGateway


@pytest.fixture
def gw():
    g = APIGateway()
    g.register_service("main-api", "http://main:5000")
    g.register_service("analytics-service", "http://analytics:5001")
    g.add_route("/api/v1/analytics", "analytics-service", requires_auth=True)
    g.add_route("/api/v1/auth", "main-api", requires_auth=False)
    g.add_route("/api/v1", "main-api", requires_auth=True)
    g.issue_token("valid-token-123")
    return g


def test_unknown_route_returns_404(gw):
    result = gw.handle("/nowhere", "1.2.3.4")
    assert result["status"] == 404


def test_public_route_no_token_needed(gw):
    result = gw.handle("/api/v1/auth/login", "1.2.3.4")
    assert result["status"] == 200
    assert result["routed_to"]["service"] == "main-api"


def test_protected_route_without_token_rejected(gw):
    result = gw.handle("/api/v1/chats/1", "1.2.3.4")
    assert result["status"] == 401


def test_protected_route_with_valid_token_routes_correctly(gw):
    result = gw.handle("/api/v1/chats/1", "1.2.3.4", auth_token="valid-token-123")
    assert result["status"] == 200
    assert result["routed_to"]["service"] == "main-api"


def test_more_specific_route_wins_over_general_one(gw):
    """/api/v1/analytics should route to analytics-service, not main-api,
    even though /api/v1 also matches as a prefix."""
    result = gw.handle("/api/v1/analytics/summary", "1.2.3.4", auth_token="valid-token-123")
    assert result["status"] == 200
    assert result["routed_to"]["service"] == "analytics-service"


def test_rate_limit_blocks_after_threshold():
    g = APIGateway()
    g.rate_limiter.max_requests = 3
    g.register_service("main-api", "http://main:5000")
    g.add_route("/api/v1", "main-api", requires_auth=False)

    results = [g.handle("/api/v1/ping", "5.5.5.5") for _ in range(5)]
    statuses = [r["status"] for r in results]
    assert statuses[:3] == [200, 200, 200]
    assert statuses[3] == 429
    assert statuses[4] == 429


def test_no_healthy_instance_returns_503():
    g = APIGateway()
    g.add_route("/api/v1", "ghost-service", requires_auth=False)
    result = g.handle("/api/v1/x", "1.2.3.4")
    assert result["status"] == 503


def test_requests_are_logged(gw):
    gw.handle("/api/v1/auth/login", "9.9.9.9")
    recent = gw.log.recent(1)
    assert len(recent) == 1
    assert recent[0]["client_ip"] == "9.9.9.9"
    assert "duration_ms" in recent[0]


def test_different_clients_have_independent_rate_limits():
    g = APIGateway()
    g.rate_limiter.max_requests = 1
    g.register_service("main-api", "http://main:5000")
    g.add_route("/api/v1", "main-api", requires_auth=False)

    r1 = g.handle("/api/v1/x", "1.1.1.1")
    r2 = g.handle("/api/v1/x", "2.2.2.2")
    assert r1["status"] == 200
    assert r2["status"] == 200  # different client, own budget


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
