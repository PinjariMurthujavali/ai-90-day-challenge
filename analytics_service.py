"""
DAY 41: Microservices Architecture Intro
============================================
Splits one piece of the monolith (analytics/stats) out into its own
independently-deployable Flask service, and introduces a lightweight
in-memory Service Registry so services can discover each other by name
instead of hardcoded URLs.

This is intentionally small and self-contained — a real "first microservice"
extracted from api.py, not a toy example — to demonstrate the core ideas:
  - Independent deployability (own file, own port, own process)
  - Own data ownership (computes from the same DB but exposes it via its own API)
  - Service discovery (register/lookup by name instead of hardcoded host:port)
  - Inter-service HTTP calls (the main API calls this service over HTTP)

Run standalone:
    python analytics_service.py          # starts on port 5001

Run tests:
    pytest test_microservices.py -v
"""

import sqlite3
import time
from flask import Flask, jsonify, request

DB_FILE = "chatbot.db"


# ============================================
# SERVICE REGISTRY (in-memory service discovery)
# ============================================

class ServiceRegistry:
    """
    Minimal service discovery: services register themselves by name with a
    base URL, other services look them up by name instead of hardcoding
    hosts. In production this role is played by Consul, etcd, or Kubernetes
    DNS — this is the same idea, simplified to fit in one file.
    """

    def __init__(self):
        self._services = {}  # name -> {url, registered_at, last_heartbeat}

    def register(self, name, url):
        self._services[name] = {
            "url": url,
            "registered_at": time.time(),
            "last_heartbeat": time.time(),
        }
        return {"name": name, "url": url, "status": "registered"}

    def heartbeat(self, name):
        if name in self._services:
            self._services[name]["last_heartbeat"] = time.time()
            return True
        return False

    def discover(self, name):
        entry = self._services.get(name)
        if not entry:
            return None
        # Consider a service "down" if it hasn't heartbeated in 30s
        if time.time() - entry["last_heartbeat"] > 30:
            return None
        return entry["url"]

    def list_services(self):
        now = time.time()
        return {
            name: {
                "url": info["url"],
                "healthy": (now - info["last_heartbeat"]) <= 30,
                "last_heartbeat_ago_s": round(now - info["last_heartbeat"], 1),
            }
            for name, info in self._services.items()
        }


registry = ServiceRegistry()


# ============================================
# ANALYTICS MICROSERVICE
# ============================================
# This is its own Flask app — could be deployed on a completely separate
# server/container from the main api.py, with its own scaling, its own
# deploy schedule, its own crash blast-radius.

app = Flask(__name__)


def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"service": "analytics-service", "status": "healthy"})


@app.route("/register", methods=["POST"])
def register_self():
    """A service calls this on startup to announce itself to the registry."""
    data = request.get_json(force=True, silent=True) or {}
    name = data.get("name")
    url = data.get("url")
    if not name or not url:
        return jsonify({"error": "name and url are required"}), 400
    return jsonify(registry.register(name, url))


@app.route("/registry", methods=["GET"])
def list_registry():
    return jsonify(registry.list_services())


@app.route("/discover/<name>", methods=["GET"])
def discover(name):
    url = registry.discover(name)
    if not url:
        return jsonify({"error": f"service '{name}' not found or unhealthy"}), 404
    return jsonify({"name": name, "url": url})


@app.route("/analytics/summary", methods=["GET"])
def analytics_summary():
    """The actual business logic this microservice owns: platform-wide stats."""
    conn = get_connection()
    try:
        total_users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
        total_chats = conn.execute("SELECT COUNT(*) c FROM chats").fetchone()["c"]
        total_messages = conn.execute("SELECT COUNT(*) c FROM messages").fetchone()["c"]
    except sqlite3.OperationalError:
        total_users = total_chats = total_messages = 0
    finally:
        conn.close()

    return jsonify({
        "service": "analytics-service",
        "total_users": total_users,
        "total_chats": total_chats,
        "total_messages": total_messages,
        "generated_at": time.time(),
    })


@app.route("/analytics/user/<int:user_id>", methods=["GET"])
def user_analytics(user_id):
    conn = get_connection()
    try:
        chat_count = conn.execute(
            "SELECT COUNT(*) c FROM chats WHERE user_id = ?", (user_id,)
        ).fetchone()["c"]
    except sqlite3.OperationalError:
        chat_count = 0
    finally:
        conn.close()
    return jsonify({"user_id": user_id, "chat_count": chat_count})


# ============================================
# EXAMPLE: how the MAIN api.py would call this service
# ============================================

def call_analytics_service_example():
    """
    Demonstrates the inter-service call pattern api.py would use:
    look the service up by name (not a hardcoded URL), then call it over HTTP.
    """
    import requests
    url = registry.discover("analytics-service")
    if not url:
        return {"error": "analytics-service not registered"}
    try:
        resp = requests.get(f"{url}/analytics/summary", timeout=3)
        return resp.json()
    except Exception as e:
        return {"error": f"analytics-service unreachable: {e}"}


if __name__ == "__main__":
    # Self-register on startup, like a real microservice would
    registry.register("analytics-service", "http://localhost:5001")
    app.run(port=5001, debug=True)
