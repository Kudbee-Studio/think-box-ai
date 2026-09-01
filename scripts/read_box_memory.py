import sqlite3
conn = sqlite3.connect("/workspace/home/thinkbox_memory.db")
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print("Tables:", tables)
print()
for t in tables:
    print(f"=== {t} ===")
    schema = conn.execute(f"SELECT sql FROM sqlite_master WHERE name='{t}'").fetchone()
    if schema: print(schema[0])
    count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"Rows: {count}")
    if count > 0:
        rows = conn.execute(f"SELECT * FROM {t} LIMIT 5").fetchall()
        cols = [d[0] for d in conn.execute(f"SELECT * FROM {t} LIMIT 1").description]
        print(f"Cols: {cols}")
        for r in rows: print(r)
    print()
conn.close()
