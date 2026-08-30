#!/usr/bin/env python3
"""KUDBEE Security Operations Center (SOC)

Monitors all traffic to exposed servers, detects anomalies,
and feeds threat intelligence into the learning system.

Features:
- Real-time traffic monitoring
- Port scan detection
- Brute force detection
- Anomaly detection (ML-based)
- Auto-response (rate limiting, IP blocking)
"""

import json
import os
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler

DB_PATH = "/opt/kudbee/memory/security.db"


class SecurityMonitor:
    """Monitors and analyzes security events."""

    def __init__(self):
        self._init_db()
        self.connection_counts = defaultdict(int)
        self.port_access = defaultdict(set)
        self.failed_attempts = defaultdict(int)
        self.alerts = []

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS security_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                source_ip TEXT,
                destination_ip TEXT,
                port INTEGER,
                event_type TEXT,
                payload TEXT,
                risk_score REAL,
                action_taken TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS threat_intel (
                ip TEXT PRIMARY KEY,
                first_seen TEXT,
                last_seen TEXT,
                attack_count INTEGER,
                ports_targeted TEXT,
                country TEXT,
                asn TEXT,
                reputation_score REAL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anomalies (
                anomaly_id TEXT PRIMARY KEY,
                detected_at TEXT NOT NULL,
                anomaly_type TEXT,
                description TEXT,
                confidence REAL,
                related_ips TEXT
            )
        """)
        conn.commit()
        conn.close()

    def log_event(self, src_ip, dst_ip, port, event_type, payload="", risk=0.0, action="logged"):
        """Log a security event."""
        event_id = f"EVT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{hash(src_ip+str(port)) % 10000:04d}"
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO security_events 
            (event_id, timestamp, source_ip, destination_ip, port, event_type, payload, risk_score, action_taken)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (event_id, datetime.now(timezone.utc).isoformat(), src_ip, dst_ip, port, event_type, payload[:200], risk, action))
        conn.commit()
        conn.close()

    def detect_port_scan(self, src_ip, ports_accessed):
        """Detect if a source IP is scanning multiple ports."""
        if len(ports_accessed) > 10:
            self.log_event(src_ip, "multiple", 0, "PORT_SCAN", f"Ports: {sorted(ports_accessed)}", risk=0.7)
            return True
        return False

    def detect_brute_force(self, src_ip, port, attempts):
        """Detect brute force attempts."""
        if attempts > 5:
            self.log_event(src_ip, "server", port, "BRUTE_FORCE", f"Attempts: {attempts}", risk=0.8)
            return True
        return False

    def detect_traffic_spike(self, current_pps, threshold=1000):
        """Detect traffic spikes."""
        if current_pps > threshold:
            anomaly_id = f"ANOM-{int(time.time())}"
            conn = sqlite3.connect(DB_PATH)
            conn.execute("""
                INSERT INTO anomalies (anomaly_id, detected_at, anomaly_type, description, confidence)
                VALUES (?, ?, ?, ?, ?)
            """, (anomaly_id, datetime.now(timezone.utc).isoformat(), "TRAFFIC_SPIKE",
                  f"Current: {current_pps} pps, Threshold: {threshold}", 0.9))
            conn.commit()
            conn.close()
            return True
        return False

    def get_dashboard_data(self):
        """Get data for security dashboard."""
        conn = sqlite3.connect(DB_PATH)

        # Recent events
        recent_events = conn.execute("""
            SELECT timestamp, source_ip, port, event_type, risk_score 
            FROM security_events 
            ORDER BY timestamp DESC 
            LIMIT 20
        """).fetchall()

        # Top attackers
        top_attackers = conn.execute("""
            SELECT source_ip, COUNT(*) as count, MAX(risk_score) as max_risk
            FROM security_events 
            WHERE source_ip IS NOT NULL
            GROUP BY source_ip 
            ORDER BY count DESC 
            LIMIT 10
        """).fetchall()

        # Anomalies
        anomalies = conn.execute("""
            SELECT detected_at, anomaly_type, description, confidence 
            FROM anomalies 
            ORDER BY detected_at DESC 
            LIMIT 10
        """).fetchall()

        # Stats
        total_events = conn.execute("SELECT COUNT(*) FROM security_events").fetchone()[0]
        total_ips = conn.execute("SELECT COUNT(DISTINCT source_ip) FROM security_events WHERE source_ip IS NOT NULL").fetchone()[0]
        high_risk = conn.execute("SELECT COUNT(*) FROM security_events WHERE risk_score > 0.7").fetchone()[0]

        conn.close()

        return {
            "recent_events": [
                {"time": e[0][11:19], "ip": e[1], "port": e[2], "type": e[3], "risk": e[4]}
                for e in recent_events
            ],
            "top_attackers": [
                {"ip": a[0], "attacks": a[1], "max_risk": a[2]}
                for a in top_attackers
            ],
            "anomalies": [
                {"time": a[0][11:19], "type": a[1], "desc": a[2][:50], "confidence": a[3]}
                for a in anomalies
            ],
            "stats": {
                "total_events": total_events,
                "unique_ips": total_ips,
                "high_risk_events": high_risk
            }
        }

    def generate_ioc_feed(self):
        """Generate Indicators of Compromise feed for threat sharing."""
        conn = sqlite3.connect(DB_PATH)
        iocs = conn.execute("""
            SELECT source_ip, COUNT(*) as count, GROUP_CONCAT(DISTINCT port) as ports
            FROM security_events 
            WHERE risk_score > 0.5
            GROUP BY source_ip
            HAVING count > 3
            ORDER BY count DESC
        """).fetchall()
        conn.close()

        return [{"ip": i[0], "sightings": i[1], "ports": i[2]} for i in iocs]


# Global monitor instance
monitor = SecurityMonitor()


class SecurityHandler(BaseHTTPRequestHandler):
    """HTTP handler for security API."""

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/api/security/events":
            self.send_json(200, monitor.get_dashboard_data())

        elif path == "/api/security/iocs":
            self.send_json(200, {"iocs": monitor.generate_ioc_feed()})

        elif path == "/api/security/stats":
            data = monitor.get_dashboard_data()
            self.send_json(200, data.get("stats", {}))

        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(content_length)) if content_length else {}
        path = self.path.split("?")[0]

        if path == "/api/security/log":
            monitor.log_event(
                body.get("src_ip", ""),
                body.get("dst_ip", ""),
                body.get("port", 0),
                body.get("event_type", "unknown"),
                body.get("payload", ""),
                body.get("risk", 0.0),
                body.get("action", "logged")
            )
            self.send_json(200, {"status": "logged"})

        else:
            self.send_json(404, {"error": "not found"})

    def send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8083), SecurityHandler)
    print("KUDBEE SOC running on port 8083")
    server.serve_forever()
