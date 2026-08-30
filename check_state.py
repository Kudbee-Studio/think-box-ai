#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect("/opt/kudbee/memory/think_tokens.db")
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
print("Tables:", [r[0] for r in cur.fetchall()])

cur.execute("SELECT COUNT(*) FROM think_tokens")
print(f"Think Tokens: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM token_containers")
print(f"Containers: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM red_team_challenges")
print(f"Challenges: {cur.fetchone()[0]}")

cur.execute("SELECT COUNT(*) FROM swarm_votes")
print(f"Votes: {cur.fetchone()[0]}")

# List active tokens
cur.execute("SELECT token_id, token_type, confidence, status FROM think_tokens")
print("\nActive Tokens:")
for row in cur.fetchall():
    print(f"  {row[0]}: {row[1]} (confidence: {row[2]:.2f}, {row[3]})")

# List containers
cur.execute("SELECT container_id, token_id, status FROM token_containers")
print("\nContainers:")
for row in cur.fetchall():
    print(f"  {row[0][:8]}: {row[1]} ({row[2]})")

conn.close()
