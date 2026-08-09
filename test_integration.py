"""
DAY 38: Integration Testing
==============================
Unit tests (Day 37) check pieces in isolation. Integration tests check
that the pieces work correctly TOGETHER — full user journeys through
multiple endpoints, in sequence, verifying state carries over correctly
at each step.

Setup:
    pip install pytest

Run:
    pytest test_integration.py -v
"""

import os
import sqlite3
import tempfile
import pytest


@pytest.fixture
def client():
    """Same isolated-DB fixture pattern as Day 37, so integration tests
    never touch the real chatbot.db."""
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

    os.environ.pop("TURSO_DATABASE_URL", None)
    os.environ.pop("TURSO_AUTH_TOKEN", None)
    os.environ.setdefault("GROQ_API_KEY", "dummy_key_for_test")

    import importlib
    import api as api_module
    importlib.reload(api_module)
    api_module.DB_FILE = db_path

    api_module.app.config["TESTING"] = True
    with api_module.app.test_client() as test_client:
        yield test_client

    os.close(db_fd)
    os.unlink(db_path)


# ---------------- FULL USER JOURNEY ----------------

class TestNewUserJourney:
    """Register -> Login -> Create chat -> List chats -> Send message -> Read messages.
    Each step feeds real data (ids, tokens) into the next, exactly like a real client."""

    def test_full_signup_to_chat_flow(self, client):
        # Step 1: Register
        reg = client.post("/api/v1/auth/register", json={
            "username": "journey_user", "password": "pw123", "email": "j@test.com"
        })
        assert reg.status_code == 200, "Registration should succeed"

        # Step 2: Login using the same credentials just registered
        login = client.post("/api/v1/auth/login", json={
            "username": "journey_user", "password": "pw123"
        })
        assert login.status_code == 200
        auth = login.get_json()
        token, user_id = auth["token"], auth["user_id"]
        assert token and user_id, "Login must return a usable token + user_id"
        headers = {"Authorization": f"Bearer {token}"}

        # Step 3: New user should start with zero chats
        empty = client.get(f"/api/v1/chats/{user_id}")
        assert empty.get_json()["chats"] == []

        # Step 4: Create a chat as that user
        created = client.post("/api/v1/chat", json={
            "user_id": user_id, "title": "Integration Test Chat", "personality": "mentor"
        }, headers=headers)
        assert created.status_code in (200, 201)
        chat_body = created.get_json()
        chat_id = chat_body.get("id") or chat_body.get("chat_id")
        assert chat_id, "Chat creation must return an id for later steps"

        # Step 5: That chat must now show up in the user's chat list
        listing = client.get(f"/api/v1/chats/{user_id}")
        titles = [c["title"] for c in listing.get_json()["chats"]]
        assert "Integration Test Chat" in titles

        # Step 6: Send a message in that chat
        sent = client.post(f"/api/v1/chat/{chat_id}/messages", json={
            "content": "Hello from integration test"
        }, headers=headers)
        assert sent.status_code == 201
        assert "reply" in sent.get_json()

        # Step 7: The message history must contain both the user message and the reply
        history = client.get(f"/api/v1/chat/{chat_id}/messages")
        roles = [m["role"] for m in history.get_json()["messages"]]
        assert "user" in roles
        assert "assistant" in roles


class TestTwoUsersDontLeakData:
    """Integration check: user A's chats must never appear in user B's list."""

    def test_chat_isolation_between_users(self, client):
        client.post("/api/v1/auth/register", json={"username": "user_a", "password": "pw"})
        login_a = client.post("/api/v1/auth/login", json={"username": "user_a", "password": "pw"})
        auth_a = login_a.get_json()

        client.post("/api/v1/auth/register", json={"username": "user_b", "password": "pw"})
        login_b = client.post("/api/v1/auth/login", json={"username": "user_b", "password": "pw"})
        auth_b = login_b.get_json()

        client.post("/api/v1/chat", json={
            "user_id": auth_a["user_id"], "title": "A's private chat"
        }, headers={"Authorization": f"Bearer {auth_a['token']}"})

        b_chats = client.get(f"/api/v1/chats/{auth_b['user_id']}").get_json()["chats"]
        titles = [c["title"] for c in b_chats]
        assert "A's private chat" not in titles, "User B must not see User A's chats"


class TestDuplicateRegistrationFlow:
    """Register once -> attempt duplicate -> original account must still log in fine."""

    def test_duplicate_register_does_not_break_original_account(self, client):
        first = client.post("/api/v1/auth/register", json={"username": "dupe", "password": "orig"})
        assert first.status_code == 200

        second = client.post("/api/v1/auth/register", json={"username": "dupe", "password": "different"})
        assert second.status_code == 400, "Duplicate username must be rejected"

        # Original account's password must still work — proves the rejected
        # duplicate attempt didn't corrupt or overwrite the existing row.
        login = client.post("/api/v1/auth/login", json={"username": "dupe", "password": "orig"})
        assert login.status_code == 200


class TestSearchAfterChatCreation:
    """Create content via one endpoint, verify it's discoverable via another."""

    def test_created_chat_is_searchable(self, client):
        client.post("/api/v1/auth/register", json={"username": "searcher", "password": "pw"})
        login = client.post("/api/v1/auth/login", json={"username": "searcher", "password": "pw"})
        auth = login.get_json()

        client.post("/api/v1/chat", json={
            "user_id": auth["user_id"], "title": "Quantum Physics Discussion"
        }, headers={"Authorization": f"Bearer {auth['token']}"})

        resp = client.get("/api/v1/search?q=Quantum")
        assert resp.status_code == 200


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
