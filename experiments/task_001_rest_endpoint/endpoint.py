"""
REST Endpoint - FIXED version with parameterized queries.
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
    return {"id": item_id, "name": item.name, "description": item.description, "price": item.price, "quantity": item.quantity}

@app.get("/items/{item_id}")
def get_item(item_id: int):
    conn = sqlite3.connect("items.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, description, price, quantity FROM items WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "name": row[1], "description": row[2], "price": row[3], "quantity": row[4]}
    raise HTTPException(status_code=404, detail="Item not found")

@app.post("/search")
def search_items(request: SearchRequest):
    """
    FIXED ENDPOINT: Parameterized query prevents SQL injection.
    """
    conn = sqlite3.connect("items.db")
    cursor = conn.cursor()
    
    # FIXED: Parameterized query with LIKE placeholder
    query = "SELECT id, name, description, price, quantity FROM items WHERE name LIKE ?"
    cursor.execute(query, (f"%{request.query}%",))
    rows = cursor.fetchall()
    conn.close()
    
    return {"results": [{"id": r[0], "name": r[1], "description": r[2], "price": r[3], "quantity": r[4]} for r in rows]}

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)