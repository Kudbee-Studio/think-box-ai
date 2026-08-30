#!/usr/bin/env python3
import sqlite3
import json

conn = sqlite3.connect("/opt/kudbee/memory/kudbee.db")
cur = conn.cursor()

cur.execute("SELECT box_id, box_type, status, result FROM think_boxes")
for row in cur.fetchall():
    box_id, box_type, status, result = row
    print(f"Box: {box_id} ({box_type}) - {status}")
    if result:
        try:
            data = json.loads(result)
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(v, str) and len(v) > 100:
                        print(f"  {k}: {v[:300]}...")
                    else:
                        print(f"  {k}: {v}")
            else:
                print(f"  Result: {str(data)[:300]}")
        except:
            print(f"  Result: {result[:300]}")
    print()

conn.close()
