#!/usr/bin/env python3
"""Memory operation benchmarks for Think Box AI."""

import sqlite3
import time
import json
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "thinkbox_memory.db"

def benchmark():
    conn = sqlite3.connect(str(DB_PATH))
    
    # Ensure table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_entries (
            key TEXT PRIMARY KEY,
            layer TEXT NOT NULL,
            entry_type TEXT NOT NULL,
            value TEXT NOT NULL,
            agent_id TEXT DEFAULT '',
            task_id TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            confidence REAL DEFAULT 1.0
        )
    """)
    
    results = {}
    
    # Benchmark 1: Write 1000 entries
    start = time.perf_counter()
    for i in range(1000):
        conn.execute(
            "INSERT OR REPLACE INTO memory_entries VALUES (?,?,?,?,?,?,?,?,?)",
            (f"bench_key_{i}", "benchmark", "test", f"value_{i}", "bench", "bench", "2026-09-01T00:00:00Z", "{}", 1.0)
        )
    conn.commit()
    results["write_1000"] = round(time.perf_counter() - start, 4)
    
    # Benchmark 2: Read by key (indexed)
    start = time.perf_counter()
    for i in range(1000):
        conn.execute("SELECT value FROM memory_entries WHERE key=?", (f"bench_key_{i}",)).fetchone()
    results["read_1000_by_key"] = round(time.perf_counter() - start, 4)
    
    # Benchmark 3: Search by layer (full table scan)
    start = time.perf_counter()
    conn.execute("SELECT * FROM memory_entries WHERE layer='benchmark'").fetchall()
    results["search_by_layer"] = round(time.perf_counter() - start, 4)
    
    # Benchmark 4: Count all
    start = time.perf_counter()
    conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()
    results["count_all"] = round(time.perf_counter() - start, 4)
    
    # Benchmark 5: Delete all benchmark entries
    start = time.perf_counter()
    conn.execute("DELETE FROM memory_entries WHERE layer='benchmark'")
    conn.commit()
    results["delete_1000"] = round(time.perf_counter() - start, 4)
    
    # Final count
    final = conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0]
    
    conn.close()
    
    print("=== Memory Benchmark Results ===")
    for op, duration in results.items():
        print(f"  {op}: {duration}s")
    print(f"  Final row count: {final}")
    
    return results

if __name__ == "__main__":
    benchmark()
