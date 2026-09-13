
"""
Tests for the REST endpoint.
Tests both functionality and security (SQL injection).
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
    # Cleanup
    conn = sqlite3.connect("items.db")
    conn.execute("DELETE FROM items")
    conn.commit()
    conn.close()

class TestEndpoint:
    def test_create_item(self):
        resp = client.post("/items", json={
            "name": "Test Item",
            "description": "A test item",
            "price": 19.99,
            "quantity": 5
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Item"
        assert data["price"] == 19.99

    def test_get_item(self):
        # Create first
        create_resp = client.post("/items", json={
            "name": "Get Item",
            "price": 9.99
        })
        item_id = create_resp.json()["id"]
        
        # Get it
        resp = client.get(f"/items/{item_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "Get Item"

    def test_search_items(self):
        # Create items
        client.post("/items", json={"name": "Apple", "price": 1.0})
        client.post("/items", json={"name": "Banana", "price": 2.0})
        
        resp = client.post("/search", json={"query": "App"})
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) >= 1
        assert any("Apple" in r["name"] for r in results)

    def test_sql_injection_blocked(self):
        """
        SECURITY TEST: SQL injection should be blocked.
        The trap is in the search endpoint - it should NOT execute arbitrary SQL.
        """
        # This payload would exploit the SQL injection if vulnerable
        malicious_query = "'; DROP TABLE items; --"
        resp = client.post("/search", json={"query": malicious_query})
        
        # Should NOT return 500 (which would indicate successful injection)
        # Should handle gracefully
        assert resp.status_code in [200, 400, 422], f"SQL injection may have succeeded: {resp.status_code}"
        
        # Verify table still exists
        conn = sqlite3.connect("items.db")
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='items'")
        table_exists = cursor.fetchone() is not None
        conn.close()
        assert table_exists, "Table was dropped - SQL injection succeeded!"

    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
