"""Tests for Day 41: Microservices Architecture Intro."""

import os
import sqlite3
import tempfile
import pytest


@pytest.fixture
def client():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);
        CREATE TABLE chats (id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT);
        CREATE TABLE messages (id INTEGER PRIMARY KEY, chat_id INTEGER, content TEXT);
        INSERT INTO users (username) VALUES ('a'), ('b');
        INSERT INTO chats (user_id, title) VALUES (1, 'chat1'), (1, 'chat2');
        INSERT INTO messages (chat_id, content) VALUES (1, 'hi'), (1, 'hello'), (2, 'yo');
        """
    )
    conn.commit()
    conn.close()

    import importlib
    import analytics_service as svc
    importlib.reload(svc)
    svc.DB_FILE = db_path

    with svc.app.test_client() as c:
        yield c, svc

    os.close(db_fd)
    os.unlink(db_path)


def test_health(client):
    c, svc = client
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "healthy"


def test_analytics_summary(client):
    c, svc = client
    resp = c.get("/analytics/summary")
    body = resp.get_json()
    assert body["total_users"] == 2
    assert body["total_chats"] == 2
    assert body["total_messages"] == 3


def test_user_analytics(client):
    c, svc = client
    resp = c.get("/analytics/user/1")
    assert resp.get_json()["chat_count"] == 2


def test_service_registry_register_and_discover(client):
    c, svc = client
    svc.registry.register("test-service", "http://localhost:9999")
    url = svc.registry.discover("test-service")
    assert url == "http://localhost:9999"


def test_service_registry_unknown_service(client):
    c, svc = client
    assert svc.registry.discover("does-not-exist") is None


def test_register_endpoint(client):
    c, svc = client
    resp = c.post("/register", json={"name": "chat-service", "url": "http://localhost:5002"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "registered"

    listing = c.get("/registry").get_json()
    assert "chat-service" in listing


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
