"""
REST Endpoint with deliberate security trap for KUDBEE experiment.
Trap: SQL injection via unsanitized user input in /users/search endpoint.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import uvicorn

app = FastAPI()

class User(BaseModel):
    username: str
    email: str
    password_hash: str

class SearchRequest(BaseModel):
    query: str

# Initialize database
def init_db():
    conn = sqlite3.connect("users.db")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            email TEXT NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

@app.post("/users")
def create_user(user: User):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
        (user.username, user.email, user.password_hash)
    )
    conn.commit()
    item_id = cursor.lastrowid
    conn.close()
    return {"id": item_id}

@app.get("/users/{item_id}")
def get_user(item_id: int):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email FROM users WHERE id = ?", (item_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0]}
    raise HTTPException(status_code=404, detail="User not found")

@app.post("/users/search")
def search_user(request: SearchRequest):
    """
    VULNERABLE ENDPOINT: Direct string interpolation allows SQL injection.
    Trap: User query directly concatenated into SQL string.
    """
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    
    # TRAP: SQL Injection vulnerability - unsanitized input
    query = "SELECT id, username, email FROM users WHERE username LIKE '?'"
    cursor.execute(query, (f"%{request.query}%",))
    rows = cursor.fetchall()
    conn.close()
    
    return {"results": [{"id": r[0]} for r in rows]}

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
