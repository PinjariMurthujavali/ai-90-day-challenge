"""
DAY 43: API Gateway Implementation
=====================================
Brings together everything built so far into a single front door:

  - Routing        : one entry point maps incoming paths to the right
                      backend microservice (Day 41's registry)
  - Load balancing : picks which instance of that service to hit (Day 42)
  - Rate limiting   : per-client throttling before any backend is touched (Day 30)
  - Auth checking   : validates a token once, at the edge, so individual
                      services don't each have to re-implement it
  - Request logging : every request that passes through gets logged with
                      timing, for the kind of visibility real API gateways
                      (Kong, AWS API Gateway, nginx) give you for free

Run standalone:
    python api_gateway.py       # starts on port 8000

Run tests:
    pytest test_gateway.py -v
"""

import time
import uuid
from collections import defaultdict, deque
from flask import Flask, jsonify, request

from load_balancer import LoadBalancedRegistry


# ============================================
# GATEWAY RATE LIMITER (same sliding-window idea as Day 30, gateway-scoped)
# ============================================

class GatewayRateLimiter:
    def __init__(self, max_requests=30, window_seconds=60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = defaultdict(deque)

    def allow(self, client_key):
        now = time.time()
        q = self.requests[client_key]
        while q and q[0] <= now - self.window_seconds:
            q.popleft()
        if len(q) < self.max_requests:
            q.append(now)
            return True
        return False


# ============================================
# ROUTE TABLE
# ============================================

class RouteTable:
    """Maps a URL prefix to a backend service name registered in the LoadBalancedRegistry."""

    def __init__(self):
        self._routes = []  # list of (prefix, service_name, requires_auth)

    def add_route(self, prefix, service_name, requires_auth=True):
        self._routes.append((prefix, service_name, requires_auth))
        # Longest prefix first, so /api/v1/chat/x doesn't accidentally match /api/v1/chat
        self._routes.sort(key=lambda r: -len(r[0]))

    def match(self, path):
        for prefix, service_name, requires_auth in self._routes:
            if path.startswith(prefix):
                return service_name, requires_auth
        return None, None


# ============================================
# REQUEST LOG (in-memory, for observability)
# ============================================

class RequestLog:
    def __init__(self, capacity=200):
        self.capacity = capacity
        self.entries = deque(maxlen=capacity)

    def record(self, **fields):
        fields["logged_at"] = time.time()
        self.entries.append(fields)

    def recent(self, n=20):
        return list(self.entries)[-n:]


# ============================================
# THE GATEWAY ITSELF
# ============================================

class APIGateway:
    def __init__(self):
        self.registry = LoadBalancedRegistry(strategy="round_robin")
        self.routes = RouteTable()
        self.rate_limiter = GatewayRateLimiter(max_requests=30, window_seconds=60)
        self.log = RequestLog()
        self.valid_tokens = set()  # populated by the auth service in a real system

    # ---- setup ----
    def register_service(self, name, url, weight=1):
        return self.registry.register(name, url, weight=weight)

    def add_route(self, prefix, service_name, requires_auth=True):
        self.routes.add_route(prefix, service_name, requires_auth)

    def issue_token(self, token):
        """Test/demo hook to simulate a token being valid (a real gateway
        would verify against the auth service instead)."""
        self.valid_tokens.add(token)

    # ---- the actual gateway decision pipeline ----
    def handle(self, path, client_ip, auth_token=None):
        """
        Runs an incoming request through the full gateway pipeline and
        returns a dict describing what WOULD happen (status code, and if
        successful, which backend instance it would be forwarded to).
        This is deliberately transport-agnostic so it's testable without
        a live HTTP server, and the Flask layer below just wraps it.
        """
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()

        # 1. Rate limit at the edge, before touching any backend
        if not self.rate_limiter.allow(client_ip):
            result = {"request_id": request_id, "status": 429, "error": "Rate limit exceeded"}
            self._log(path, client_ip, result, start)
            return result

        # 2. Route resolution
        service_name, requires_auth = self.routes.match(path)
        if not service_name:
            result = {"request_id": request_id, "status": 404, "error": "No route matches this path"}
            self._log(path, client_ip, result, start)
            return result

        # 3. Auth check at the edge (services behind the gateway can trust this already happened)
        if requires_auth and auth_token not in self.valid_tokens:
            result = {"request_id": request_id, "status": 401, "error": "Invalid or missing token"}
            self._log(path, client_ip, result, start)
            return result

        # 4. Load-balanced instance selection
        instance_url = self.registry.get_instance(service_name)
        if not instance_url:
            result = {"request_id": request_id, "status": 503, "error": f"No healthy instances for '{service_name}'"}
            self._log(path, client_ip, result, start)
            return result

        result = {
            "request_id": request_id,
            "status": 200,
            "routed_to": {"service": service_name, "instance": instance_url},
        }
        self._log(path, client_ip, result, start)
        return result

    def _log(self, path, client_ip, result, start_time):
        self.log.record(
            path=path,
            client_ip=client_ip,
            status=result["status"],
            duration_ms=round((time.perf_counter() - start_time) * 1000, 3),
            request_id=result["request_id"],
        )


gateway = APIGateway()


# ============================================
# FLASK WRAPPER (the actual HTTP-facing gateway)
# ============================================

app = Flask(__name__)


@app.route("/gateway/health", methods=["GET"])
def gateway_health():
    return jsonify({"gateway": "healthy", "routes": len(gateway.routes._routes)})


@app.route("/gateway/logs", methods=["GET"])
def gateway_logs():
    return jsonify(gateway.log.recent(20))


@app.route("/<path:path>", methods=["GET", "POST", "PUT", "DELETE"])
def catch_all(path):
    full_path = f"/{path}"
    client_ip = request.remote_addr or "unknown"
    auth_header = request.headers.get("Authorization", "").replace("Bearer ", "")

    decision = gateway.handle(full_path, client_ip, auth_header)
    status = decision["status"]

    if status == 200:
        # In a real gateway this is where you'd actually forward the request
        # (via requests.request(...)) to decision["routed_to"]["instance"].
        return jsonify({
            "message": "Request would be forwarded",
            "request_id": decision["request_id"],
            "routed_to": decision["routed_to"],
        }), 200

    return jsonify({"request_id": decision["request_id"], "error": decision.get("error")}), status


if __name__ == "__main__":
    # Example wiring: register backend services + routes, like a real deployment would
    gateway.register_service("analytics-service", "http://localhost:5001")
    gateway.register_service("main-api", "http://localhost:5000")

    gateway.add_route("/api/v1/analytics", "analytics-service", requires_auth=True)
    gateway.add_route("/api/v1/auth", "main-api", requires_auth=False)
    gateway.add_route("/api/v1", "main-api", requires_auth=True)

    app.run(port=8000, debug=True)
