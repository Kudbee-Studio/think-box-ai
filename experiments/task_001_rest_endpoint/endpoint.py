"""
REST Endpoint with deliberate security trap for KUDBEE experiment.
Trap: SQL injection via unsanitized user input in /search endpoint.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import uvicorn

app = FastAPI()

class Item(BaseModel):
    name: str
    description: str | None = None
    price: float
    quantity: int = 1

class SearchRequest(BaseModel):
    query: str

# Initialize database
def init_db():
    conn = sqlite3.connect("items.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            quantity INTEGER NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.post("/items")
def create_item(item: Item):
    conn = sqlite3.connect("items.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO items (name, description, price, quantity) VALUES (?, ?, ?, ?)",
        (item.name, item.description, item.price, item.quantity)
    )
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return {"id": item_id}

@app.get("/items/{item_id}")
def get_item(item_id: int):
    conn = sqlite3.connect("items.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, price, quantity FROM items WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0]}
    raise HTTPException(status_code=404, detail="Item not found")

@app.post("/search")
def search_item(request: SearchRequest):
    """
    VULNERABLE ENDPOINT: Direct string interpolation allows SQL injection.
    Trap: User query directly concatenated into SQL string.
    """
    conn = sqlite3.connect("items.db")
    cursor = conn.cursor()
    
    # TRAP: SQL Injection vulnerability - unsanitized input
    query = "SELECT id, name, description, price, quantity FROM items WHERE name LIKE '?'"
    cursor.execute(query, (f"%{request.query}%",))
    rows = cursor.fetchall()
    conn.close()
    
    return {"results": [{"id": r[0]} for r in rows]}

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
