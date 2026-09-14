"""
Tests for the REST endpoint (users).
"""

import pytest
import sqlite3
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from endpoint import app, init_db

from fastapi.testclient import TestClient

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    """Reset database before each test."""
    init_db()
    yield
    conn = sqlite3.connect("users.db")
    conn.execute("DELETE FROM users")
    conn.commit()
    conn.close()

class TestEndpoint:
    def test_create_user(self):
        resp = client.post("/users", json={
            "username": "testuser",
            "email": "test@example.com",
            "password_hash": "hashed_password"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"

    def test_get_user(self):
        create_resp = client.post("/users", json={
            "username": "getuser",
            "email": "get@example.com",
            "password_hash": "hash"
        })
        user_id = create_resp.json()["id"]
        
        resp = client.get(f"/users/{user_id}")
        assert resp.status_code == 200
        assert resp.json()["username"] == "getuser"

    def test_search_users(self):
        client.post("/users", json={"username": "testuser1", "email": "test1@example.com", "password_hash": "hash1"})
        client.post("/users", json={"username": "testuser2", "email": "test2@example.com", "password_hash": "hash2"})
        
        resp = client.post("/users/search", json={"query": "test"})
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) >= 1
        assert any("testuser" in r["username"] for r in results)

    def test_sql_injection_blocked(self):
        malicious_query = "'; DROP TABLE users; --"
        resp = client.post("/users/search", json={"query": malicious_query})
        
        assert resp.status_code in [200, 400, 422], f"SQL injection may have succeeded: {resp.status_code}"
        
        conn = sqlite3.connect("users.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        table_exists = cursor.fetchone() is not None
        conn.close()
        assert table_exists, "Table was dropped - SQL injection succeeded!"

    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"