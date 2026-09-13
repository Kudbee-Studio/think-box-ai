"""
REST Endpoint with deliberate security trap for KUDBEE experiment.
Trap: SQL injection via unsanitized user input in search endpoint.
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
    user_id = cursor.lastrowid
    conn.close()
    return {"id": user_id, "username": user.username, "email": user.email}

@app.get("/users/{user_id}")
def get_user(user_id: int):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"id": row[0], "username": row[1], "email": row[2]}
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
    query = f"SELECT id, username, email FROM users WHERE username LIKE '%{request.query}%'"
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()
    
    return {"results": [{"id": r[0], "username": r[1], "email": r[2]} for r in rows]}

@app.get("/health")
def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)