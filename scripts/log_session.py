#!/usr/bin/env python3
"""Session Activity Logger — SQLite backend for cross-agent persistence.

Usage: python3 scripts/log_session.py
Writes to data/session_log.db (auto-created).
"""

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("data/session_log.db")
DB_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id    TEXT PRIMARY KEY,
    started_at    TEXT NOT NULL,
    ended_at      TEXT,
    summary       TEXT,
    agent_id      TEXT DEFAULT 'kilo',
    workspace     TEXT DEFAULT '/workspace/bcdfac4f-1903-4a17-8abf-0b10fd495578/sessions/agent_9effe633-0508-46b2-929a-9e8bb8efbc6d'
);

CREATE TABLE IF NOT EXISTS activity (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    timestamp     TEXT NOT NULL,
    category      TEXT NOT NULL,
    description   TEXT NOT NULL,
    details       TEXT DEFAULT '{}',
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS findings (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    title         TEXT NOT NULL,
    severity      TEXT NOT NULL,
    location      TEXT NOT NULL,
    description   TEXT NOT NULL,
    status        TEXT DEFAULT 'open',
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE TABLE IF NOT EXISTS deliverables (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id    TEXT NOT NULL,
    file_path     TEXT NOT NULL,
    description   TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

CREATE INDEX IF NOT EXISTS idx_activity_session ON activity(session_id);
CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON activity(timestamp);
CREATE INDEX IF NOT EXISTS idx_findings_session ON findings(session_id);
CREATE INDEX IF NOT EXISTS idx_findings_severity ON findings(severity);
"""


def init_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def main() -> None:
    conn = init_db()
    now = datetime.now(timezone.utc).isoformat()
    session_id = "agent-9effe633-20260916-security-gcode"

    with DB_LOCK:
        # ── Session ──────────────────────────────────────────────
        conn.execute(
            "INSERT OR REPLACE INTO sessions (session_id, started_at, summary, agent_id) "
            "VALUES (?, ?, ?, ?)",
            (session_id, now,
             "Security review of Think Box AI / kudbEE codebase + G-code mastery coach build",
             "kilo"),
        )

        # ── Activity Log ─────────────────────────────────────────
        activities = [
            ("security_review", "Full codebase audit: 14 findings across 4 severity levels",
             '{"files_reviewed": 40, "critical_findings": 5, "high_findings": 4}'),
            ("security_review", "Critical: Unauthenticated RCE via Node.js shell_exec",
             '{"location": "apps/web/server.ts:149-171"}'),
            ("security_review", "Critical: WebSocket header auth bypass",
             '{"location": "backend/main.py:214"}'),
            ("security_review", "Critical: SSRF via core HTTP tool",
             '{"location": "core/tools/http.py"}'),
            ("security_review", "Critical: SSRF via web server HTTP plugin",
             '{"location": "apps/web/server.ts"}'),
            ("security_review", "Critical: Raw error messages leak internal info",
             '{"affected_files": "10+"}'),
            ("security_review", "High: shell=True in setup.py",
             '{"location": "scripts/setup.py:15"}'),
            ("security_review", "High: python3/pip in shell whitelist",
             '{"location": "core/tools/shell_exec.py:18-19"}'),
            ("security_review", "Positive: Backend auth middleware well-structured",
             '{"location": "backend/security.py"}'),
            ("security_review", "Positive: No hardcoded secrets found",
             '{"search": "credential-patterns"}'),
            ("gcode_build", "Created 2-week daily drill curriculum",
             '{"file": "docs/gcode-mastery.md", "days": 14}'),
            ("gcode_build", "Created one-page safety checklist",
             '{"file": "docs/gcode-checklist.md"}'),
            ("gcode_build", "Created square.gcode — linear moves drill",
             '{"file": "examples/gcode/square.gcode", "day": 2}'),
            ("gcode_build", "Created circle.gcode — arc moves drill",
             '{"file": "examples/gcode/circle.gcode", "day": 11}'),
            ("gcode_build", "Created face.gcode — Z-level facing drill",
             '{"file": "examples/gcode/face.gcode", "day": 9}'),
            ("gcode_build", "Created peck_drill.gcode — G81/G83 canned cycles",
             '{"file": "examples/gcode/peck_drill.gcode", "day": 8}'),
            ("gcode_build", "Created pocket.gcode — pocket milling drill",
             '{"file": "examples/gcode/pocket.gcode", "day": 10}'),
            ("gcode_build", "Created README.md — dry-run guide for CAMotics/NC Viewer",
             '{"file": "examples/gcode/README.md"}'),
            ("gcode_build", "Committed all 8 files to branch kilo/amused-voxel-h11",
             '{"commit": "390ddab", "branch": "kilo/amused-voxel-h11"}'),
            ("infrastructure", "Created data/session_log.db for cross-agent persistence",
             '{"engine": "sqlite3", "pattern": "WAL-mode, threaded"}'),
        ]
        conn.executemany(
            "INSERT INTO activity (session_id, timestamp, category, description, details) "
            "VALUES (?, ?, ?, ?, ?)",
            [(session_id, now, cat, desc, det) for cat, desc, det in activities],
        )

        # ── Security Findings ────────────────────────────────────
        findings = [
            ("Unauthenticated RCE via Node.js shell_exec", "CRITICAL",
             "apps/web/server.ts:149-171",
             "execSync(command) with no whitelist, no pattern blocking, zero auth on entire server"),
            ("WebSocket header auth bypass", "CRITICAL",
             "backend/main.py:214",
             "Headers dict constructed as {key:value} instead of {'X-API-Key': key}, breaking header-based auth"),
            ("SSRF via core HTTP tool", "CRITICAL",
             "core/tools/http.py",
             "No host allowlist, no IP range block — agent can target internal services"),
            ("SSRF via web server HTTP plugin", "CRITICAL",
             "apps/web/server.ts / services/plugins.ts",
             "fetch(url) with no URL validation in Node.js layer"),
            ("Raw error messages leak internals", "CRITICAL",
             "10+ files",
             "str(e) returned directly in tool handlers — leaks paths, connection strings, IPs"),
            ("No auth on Node.js web server", "HIGH",
             "apps/web/server.ts",
             "All endpoints (REST + WebSocket) have zero authentication"),
            ("shell=True in setup script", "HIGH",
             "scripts/setup.py:15",
             "subprocess.run(cmd, shell=True) — command injection risk if cmd accepts user input"),
            ("Dangerous commands in shell whitelist", "HIGH",
             "core/tools/shell_exec.py:18-19",
             "python3, pip, git in ALLOWED_COMMANDS — can execute arbitrary code/install packages"),
            ("Governance token volatility", "HIGH",
             "thinkbox/governance_token.py:54-56",
             "In-memory token store with random per-instance signing key — tokens lost on restart"),
            ("Duplicate DEFAULT_API_KEYS definition", "MEDIUM",
             "backend/security.py:21,34",
             "Variable defined twice, line 34 silently overwrites line 21"),
            ("Default CORS origins include localhost", "MEDIUM",
             "backend/security.py:23-26",
             "Defaults to localhost origins — should be empty in production"),
            ("No CSRF protection on Node.js server", "MEDIUM",
             "apps/web/server.ts",
             "No CSRF tokens or same-origin enforcement on REST endpoints"),
            ("In-memory rate limiter", "MEDIUM",
             "backend/security.py:90",
             "Rate limit state in defaultdict(list) — lost on restart, per-instance in multi-instance deploys"),
            ("Git tool permits arbitrary operations", "MEDIUM",
             "backend/plugins/git.py",
             "checkout, commit, add operations available — can manipulate repo"),
        ]
        conn.executemany(
            "INSERT INTO findings (session_id, title, severity, location, description) "
            "VALUES (?, ?, ?, ?, ?)",
            [(session_id, title, sev, loc, desc) for title, sev, loc, desc in findings],
        )

        # ── Deliverables ─────────────────────────────────────────
        deliverables = [
            ("docs/gcode-mastery.md", "2-week daily drill curriculum (14 days, Day 1-14)"),
            ("docs/gcode-checklist.md", "One-page 'read this block' safety checklist"),
            ("examples/gcode/square.gcode", "Day 2 drill: 2x2 square, linear moves (G0/G1)"),
            ("examples/gcode/circle.gcode", "Day 11 drill: 1\" diameter circle, G3 arc with I/J"),
            ("examples/gcode/face.gcode", "Day 9 drill: 3-pass facing, Z-depth steps"),
            ("examples/gcode/peck_drill.gcode", "Day 8 drill: G81 + G83 peck drill comparison"),
            ("examples/gcode/pocket.gcode", "Day 10 drill: 1x1 square pocket, contour arcs"),
            ("examples/gcode/README.md", "Dry-run guide: CAMotics/NC Viewer, parameter table, GRBL notes"),
            ("data/session_log.db", "Cross-agent session activity logger (this database)"),
        ]
        conn.executemany(
            "INSERT INTO deliverables (session_id, file_path, description) "
            "VALUES (?, ?, ?)",
            [(session_id, path, desc) for path, desc in deliverables],
        )

        conn.commit()

    # Summary
    rows = conn.execute("SELECT category, COUNT(*) FROM activity WHERE session_id=? GROUP BY category", (session_id,)).fetchall()
    finding_count = conn.execute("SELECT COUNT(*) FROM findings WHERE session_id=?", (session_id,)).fetchone()[0]
    deliverable_count = conn.execute("SELECT COUNT(*) FROM deliverables WHERE session_id=?", (session_id,)).fetchone()[0]
    conn.close()

    print(f"\nSession logged to {DB_PATH}")
    print(f"  Activity entries: {sum(c for _, c in rows)}")
    for cat, count in rows:
        print(f"    {cat}: {count}")
    print(f"  Findings: {finding_count}")
    print(f"  Deliverables: {deliverable_count}")


if __name__ == "__main__":
    main()
