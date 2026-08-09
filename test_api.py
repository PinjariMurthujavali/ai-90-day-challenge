"""
DAY 37: Unit Testing Framework
=================================
pytest suite for the Flask REST API (api.py).

Setup:
    pip install pytest pytest-cov

Run:
    pytest test_api.py -v
    pytest test_api.py --cov=api --cov-report=term-missing   # with coverage
"""

import os
import sqlite3
import tempfile
import pytest


@pytest.fixture
def client():
    """
    Spin up the Flask app against a throwaway SQLite DB (never touches
    the real chatbot.db), yield a test client, then clean up.
    """
    db_fd, db_path = tempfile.mkstemp(suffix=".db")

    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE chats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            personality TEXT,
            is_public INTEGER DEFAULT 0,
            share_token TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            role TEXT,
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER,
            user_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.commit()
    conn.close()

    # Point both api.py and database.py at the temp DB, and force the
    # local-sqlite code path (skip Turso) so tests are fully isolated.
    os.environ.pop("TURSO_DATABASE_URL", None)
    os.environ.pop("TURSO_AUTH_TOKEN", None)

    import importlib
    import api as api_module
    importlib.reload(api_module)
    api_module.DB_FILE = db_path

    api_module.app.config["TESTING"] = True
    with api_module.app.test_client() as test_client:
        yield test_client

    os.close(db_fd)
    os.unlink(db_path)


# ---------------- AUTH TESTS ----------------

class TestAuth:
    def test_register_success(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "alice", "password": "pass123", "email": "alice@test.com"
        })
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "registered"

    def test_register_missing_fields(self, client):
        resp = client.post("/api/v1/auth/register", json={"username": "alice"})
        assert resp.status_code == 400

    def test_register_duplicate_username(self, client):
        client.post("/api/v1/auth/register", json={"username": "bob", "password": "pw1"})
        resp = client.post("/api/v1/auth/register", json={"username": "bob", "password": "pw2"})
        assert resp.status_code == 400

    def test_login_success(self, client):
        client.post("/api/v1/auth/register", json={"username": "carol", "password": "secret"})
        resp = client.post("/api/v1/auth/login", json={"username": "carol", "password": "secret"})
        assert resp.status_code == 200
        body = resp.get_json()
        assert "token" in body
        assert body["username"] == "carol"

    def test_login_wrong_password(self, client):
        client.post("/api/v1/auth/register", json={"username": "dave", "password": "correct"})
        resp = client.post("/api/v1/auth/login", json={"username": "dave", "password": "wrong"})
        assert resp.status_code == 401

    def test_login_nonexistent_user(self, client):
        resp = client.post("/api/v1/auth/login", json={"username": "ghost", "password": "x"})
        assert resp.status_code == 401


# ---------------- HEALTH CHECK ----------------

class TestHealth:
    def test_health_check(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "healthy"


# ---------------- CHATS & MESSAGES ----------------

class TestChats:
    def _register_and_login(self, client, username="erin"):
        client.post("/api/v1/auth/register", json={"username": username, "password": "pw"})
        resp = client.post("/api/v1/auth/login", json={"username": username, "password": "pw"})
        return resp.get_json()

    def test_create_chat(self, client):
        auth = self._register_and_login(client)
        resp = client.post("/api/v1/chat", json={
            "user_id": auth["user_id"], "title": "My First Chat", "personality": "mentor"
        }, headers={"Authorization": f"Bearer {auth['token']}"})
        assert resp.status_code in (200, 201)

    def test_get_chats_for_user(self, client):
        auth = self._register_and_login(client)
        client.post("/api/v1/chat", json={
            "user_id": auth["user_id"], "title": "Chat A"
        }, headers={"Authorization": f"Bearer {auth['token']}"})

        resp = client.get(f"/api/v1/chats/{auth['user_id']}")
        assert resp.status_code == 200
        assert len(resp.get_json()["chats"]) >= 1

    def test_send_message_requires_content(self, client):
        auth = self._register_and_login(client)
        create = client.post("/api/v1/chat", json={
            "user_id": auth["user_id"], "title": "Chat B"
        }, headers={"Authorization": f"Bearer {auth['token']}"})
        chat_id = create.get_json().get("id") or create.get_json().get("chat_id")

        resp = client.post(f"/api/v1/chat/{chat_id}/messages", json={},
                            headers={"Authorization": f"Bearer {auth['token']}"})
        assert resp.status_code == 400


# ---------------- ERROR HANDLING ----------------

class TestErrorHandling:
    def test_unknown_endpoint_returns_404_json(self, client):
        resp = client.get("/api/v1/does-not-exist")
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "Endpoint not found"

    def test_leaderboard_empty_db(self, client):
        resp = client.get("/api/v1/leaderboard")
        assert resp.status_code == 200
        assert resp.get_json()["leaderboard"] == []


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
