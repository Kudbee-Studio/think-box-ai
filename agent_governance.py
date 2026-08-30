#!/usr/bin/env python3
"""KUDBEE Agent Governance & State Tracking

Hardcoded deterministic rules for agent lifecycle:
- STANDBY_DORMANT: Connected, zero active tasks
- WORKING_PROCESSING: Actively executing
- BLOCKED_AWAITING_APPROVAL: HITL or rate limit
- DISCONNECTED_OFFLINE: Heartbeat > 60s
"""

import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

DB_PATH = "/opt/kudbee/memory/agent_governance.db"


class AgentState(Enum):
    STANDBY_DORMANT = "STANDBY_DORMANT"
    WORKING_PROCESSING = "WORKING_PROCESSING"
    BLOCKED_AWAITING_APPROVAL = "BLOCKED_AWAITING_APPROVAL"
    DISCONNECTED_OFFLINE = "DISCONNECTED_OFFLINE"


class AgentType(Enum):
    KILO = "kilo"
    KIMMY = "kimmy"
    CLAUDE = "claude"
    HERMES = "hermes"
    CUSTOM = "custom"
    THINK_BOX = "think_box"


class GovernanceEngine:
    """Manages agent lifecycle with hardcoded deterministic rules."""
    
    # Hardcoded limits
    MAX_HEARTBEAT_SECONDS = 60
    DORMANT_THRESHOLD_SECONDS = 300  # 5 minutes
    MAX_QUEUE_DEPTH = 10
    MAX_STEPS_PER_TASK = 50
    MAX_TOKENS_PER_TASK = 100000
    
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                agent_id TEXT PRIMARY KEY,
                agent_type TEXT NOT NULL,
                agent_name TEXT,
                state TEXT DEFAULT 'STANDBY_DORMANT',
                current_task TEXT,
                queue_depth INTEGER DEFAULT 0,
                steps_used INTEGER DEFAULT 0,
                tokens_used INTEGER DEFAULT 0,
                last_heartbeat TEXT NOT NULL,
                last_thought TEXT,
                dormant_since TEXT,
                created TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_events (
                event_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                payload TEXT,
                created TEXT NOT NULL,
                FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS task_queue (
                task_id TEXT PRIMARY KEY,
                agent_id TEXT,
                task_type TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'pending',
                steps_limit INTEGER DEFAULT 50,
                tokens_limit INTEGER DEFAULT 100000,
                steps_used INTEGER DEFAULT 0,
                tokens_used INTEGER DEFAULT 0,
                created TEXT NOT NULL,
                started TEXT,
                completed TEXT,
                error TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def register_agent(self, agent_type: str, agent_name: str) -> str:
        """Register a new agent."""
        agent_id = f"{agent_type}-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO agents 
            (agent_id, agent_type, agent_name, state, last_heartbeat, created)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (agent_id, agent_type, agent_name, AgentState.STANDBY_DORMANT.value, now, now))
        conn.commit()
        conn.close()
        
        return agent_id
    
    def heartbeat(self, agent_id: str, state: str = None, task: str = None):
        """Update agent heartbeat."""
        now = datetime.now(timezone.utc).isoformat()
        
        conn = sqlite3.connect(DB_PATH)
        
        updates = ["last_heartbeat = ?"]
        params = [now]
        
        if state:
            updates.append("state = ?")
            params.append(state)
            
            if state == AgentState.STANDBY_DORMANT.value:
                updates.append("dormant_since = ?")
                params.append(now)
                updates.append("current_task = NULL")
            elif state == AgentState.WORKING_PROCESSING.value:
                updates.append("dormant_since = NULL")
        
        if task:
            updates.append("current_task = ?")
            params.append(task)
        
        params.append(agent_id)
        
        conn.execute(f"""
            UPDATE agents SET {', '.join(updates)} WHERE agent_id = ?
        """, params)
        conn.commit()
        conn.close()
    
    def get_agent_state(self, agent_id: str) -> Optional[dict]:
        """Get current agent state with computed fields."""
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT * FROM agents WHERE agent_id = ?", (agent_id,)
        ).fetchone()
        conn.close()
        
        if not row:
            return None
        
        columns = ["agent_id", "agent_type", "agent_name", "state", "current_task",
                   "queue_depth", "steps_used", "tokens_used", "last_heartbeat",
                   "last_thought", "dormant_since", "created"]
        agent = dict(zip(columns, row))
        
        # Compute dormant duration
        last_hb = datetime.fromisoformat(agent["last_heartbeat"])
        now = datetime.now(timezone.utc)
        dormant_seconds = (now - last_hb).total_seconds()
        
        # Auto-disconnect if heartbeat too old
        if dormant_seconds > self.MAX_HEARTBEAT_SECONDS and agent["state"] != AgentState.DISCONNECTED_OFFLINE.value:
            agent["state"] = AgentState.DISCONNECTED_OFFLINE.value
        
        agent["dormant_duration_seconds"] = int(dormant_seconds)
        agent["is_dormant"] = dormant_seconds > self.DORMANT_THRESHOLD_SECONDS
        
        return agent
    
    def list_agents(self) -> list:
        """List all agents with computed states."""
        conn = sqlite3.connect(DB_PATH)
        rows = conn.execute("SELECT agent_id FROM agents").fetchall()
        conn.close()
        
        agents = []
        for row in rows:
            agent = self.get_agent_state(row[0])
            if agent:
                agents.append(agent)
        
        return agents
    
    def enqueue_task(self, task_type: str, description: str, 
                     agent_id: str = None, steps_limit: int = None, tokens_limit: int = None) -> str:
        """Add task to queue."""
        task_id = f"TASK-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO task_queue 
            (task_id, agent_id, task_type, description, steps_limit, tokens_limit, created)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (task_id, agent_id, task_type, description,
              steps_limit or self.MAX_STEPS_PER_TASK,
              tokens_limit or self.MAX_TOKENS_PER_TASK, now))
        conn.commit()
        conn.close()
        
        return task_id
    
    def get_system_health(self) -> dict:
        """Get overall system health."""
        agents = self.list_agents()
        
        states = {}
        for agent in agents:
            state = agent["state"]
            states[state] = states.get(state, 0) + 1
        
        conn = sqlite3.connect(DB_PATH)
        pending_tasks = conn.execute(
            "SELECT COUNT(*) FROM task_queue WHERE status = 'pending'"
        ).fetchone()[0]
        active_tasks = conn.execute(
            "SELECT COUNT(*) FROM task_queue WHERE status = 'running'"
        ).fetchone()[0]
        conn.close()
        
        return {
            "total_agents": len(agents),
            "states": states,
            "pending_tasks": pending_tasks,
            "active_tasks": active_tasks,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# Global engine
engine = GovernanceEngine()


class GovernanceHandler(BaseHTTPRequestHandler):
    """HTTP handler for governance API."""
    
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/api/agents":
            agents = engine.list_agents()
            self.send_json(200, {"agents": agents})
        
        elif parsed.path == "/api/health":
            health = engine.get_system_health()
            self.send_json(200, health)
        
        elif parsed.path.startswith("/api/agent/"):
            agent_id = parsed.path.split("/")[-1]
            agent = engine.get_agent_state(agent_id)
            if agent:
                self.send_json(200, agent)
            else:
                self.send_json(404, {"error": "Agent not found"})
        
        elif parsed.path == "/api/tasks":
            conn = sqlite3.connect(DB_PATH)
            rows = conn.execute(
                "SELECT * FROM task_queue ORDER BY created DESC LIMIT 20"
            ).fetchall()
            conn.close()
            
            tasks = []
            for row in rows:
                tasks.append({
                    "task_id": row[0], "agent_id": row[1], "task_type": row[2],
                    "description": row[3], "status": row[4], "steps_used": row[7],
                    "tokens_used": row[8], "created": row[9]
                })
            self.send_json(200, {"tasks": tasks})
        
        else:
            self.send_json(404, {"error": "not found"})
    
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body) if body else {}
        
        if self.path == "/api/agent/register":
            agent_id = engine.register_agent(
                data.get("agent_type", "custom"),
                data.get("agent_name", "unnamed")
            )
            self.send_json(200, {"agent_id": agent_id})
        
        elif self.path == "/api/agent/heartbeat":
            engine.heartbeat(
                data.get("agent_id"),
                data.get("state"),
                data.get("current_task")
            )
            self.send_json(200, {"status": "ok"})
        
        elif self.path == "/api/task/enqueue":
            task_id = engine.enqueue_task(
                data.get("task_type", "generic"),
                data.get("description", ""),
                data.get("agent_id"),
                data.get("steps_limit"),
                data.get("tokens_limit")
            )
            self.send_json(200, {"task_id": task_id})
        
        else:
            self.send_json(404, {"error": "not found"})
    
    def send_json(self, code, data):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        pass


def start_governance_server(port=8081):
    """Start the governance API server."""
    server = HTTPServer(("0.0.0.0", port), GovernanceHandler)
    print(f"KUDBEE Governance Server running on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    # Register some default agents
    try:
        engine.register_agent("kilo", "Kilo-Primary")
        engine.register_agent("think_box", "Director-Box")
        engine.register_agent("think_box", "Editor-Box")
        engine.register_agent("think_box", "Jury-Box")
    except:
        pass
    
    start_governance_server()
