#!/usr/bin/env python3
"""KUDBEE Memory Architecture — SIM + Elastic Cache + Think Commons

Layer 0: Agent Working Memory (current task)
Layer 1: Elastic Cache (hot context, frequently accessed)
Layer 2: Think Box Memory (persistent per-box knowledge)
Layer 3: THINK COMMONS (governed collective intelligence)
Layer 4: Raw Documents / Artifacts / Evidence
"""

import json
import os
import time
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = "/opt/kudbee/memory"
DB_PATH = f"{BASE_DIR}/kudbee.db"


class MemoryLayer:
    """Base class for all memory layers."""
    
    def __init__(self, name: str, layer_id: int):
        self.name = name
        self.layer_id = layer_id
    
    def store(self, key: str, value: Any, metadata: dict = None) -> dict:
        raise NotImplementedError
    
    def retrieve(self, key: str) -> dict:
        raise NotImplementedError
    
    def search(self, query: str, limit: int = 10) -> list:
        raise NotImplementedError


class WorkingMemory(MemoryLayer):
    """L0: What the agent is doing RIGHT NOW."""
    
    def __init__(self):
        super().__init__("Working Memory", 0)
        self.current_task = None
        self.context = {}
        self.start_time = datetime.now(timezone.utc).isoformat()
    
    def set_task(self, task: str):
        self.current_task = task
        self.context["task"] = task
        self.context["started"] = datetime.now(timezone.utc).isoformat()
    
    def update(self, key: str, value: Any):
        self.context[key] = {
            "value": value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_context(self) -> dict:
        return {
            "task": self.current_task,
            "context": self.context,
            "started": self.start_time
        }


class ElasticCache(MemoryLayer):
    """L1: Hot context that learns what the agent repeatedly accesses."""
    
    def __init__(self, db_path: str):
        super().__init__("Elastic Cache", 1)
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS elastic_cache (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT NOT NULL,
                created TEXT NOT NULL,
                ttl INTEGER DEFAULT 86400
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS access_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                accessed_at TEXT NOT NULL,
                context TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def store(self, key: str, value: Any, metadata: dict = None) -> dict:
        conn = sqlite3.connect(self.db_path)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT OR REPLACE INTO elastic_cache (key, value, access_count, last_accessed, created)
            VALUES (?, ?, COALESCE((SELECT access_count FROM elastic_cache WHERE key = ?), 0), ?, ?)
        """, (key, json.dumps(value), key, now, now))
        conn.commit()
        conn.close()
        return {"stored": key, "layer": self.layer_id}
    
    def retrieve(self, key: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        now = datetime.now(timezone.utc).isoformat()
        
        # Update access count
        conn.execute("""
            UPDATE elastic_cache 
            SET access_count = access_count + 1, last_accessed = ?
            WHERE key = ?
        """, (now, key))
        
        # Log access
        conn.execute("""
            INSERT INTO access_log (key, accessed_at) VALUES (?, ?)
        """, (key, now))
        
        row = conn.execute(
            "SELECT value, access_count FROM elastic_cache WHERE key = ?", (key,)
        ).fetchone()
        conn.commit()
        conn.close()
        
        if row:
            return {
                "key": key,
                "value": json.loads(row[0]),
                "access_count": row[1],
                "layer": self.layer_id
            }
        return None
    
    def get_hot_keys(self, min_access: int = 3) -> list:
        """Get frequently accessed keys (hot context)."""
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute("""
            SELECT key, access_count, last_accessed 
            FROM elastic_cache 
            WHERE access_count >= ?
            ORDER BY access_count DESC
            LIMIT 20
        """, (min_access,)).fetchall()
        conn.close()
        return [{"key": r[0], "access_count": r[1], "last_accessed": r[2]} for r in rows]


class ThinkBoxMemory(MemoryLayer):
    """L2: Persistent per-box knowledge that survives agent restarts."""
    
    def __init__(self, box_id: str, db_path: str):
        super().__init__("Think Box Memory", 2)
        self.box_id = box_id
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS thinkbox_memory (
                box_id TEXT NOT NULL,
                category TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                proof_hash TEXT,
                confidence REAL DEFAULT 0.5,
                created TEXT NOT NULL,
                updated TEXT NOT NULL,
                PRIMARY KEY (box_id, category, key)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS episodic_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                box_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT NOT NULL,
                context TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    
    def store(self, category: str, key: str, value: Any, 
              proof: str = None, confidence: float = 0.5) -> dict:
        conn = sqlite3.connect(self.db_path)
        now = datetime.now(timezone.utc).isoformat()
        proof_hash = hashlib.sha256(proof.encode()).hexdigest()[:16] if proof else None
        
        conn.execute("""
            INSERT OR REPLACE INTO thinkbox_memory 
            (box_id, category, key, value, proof_hash, confidence, created, updated)
            VALUES (?, ?, ?, ?, ?, ?, 
                COALESCE((SELECT created FROM thinkbox_memory WHERE box_id=? AND category=? AND key=?), ?),
                ?)
        """, (self.box_id, category, key, json.dumps(value), proof_hash, confidence,
              self.box_id, category, key, now, now))
        conn.commit()
        conn.close()
        return {"stored": f"{self.box_id}/{category}/{key}", "layer": self.layer_id}
    
    def retrieve(self, category: str, key: str) -> dict:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("""
            SELECT value, proof_hash, confidence, created, updated
            FROM thinkbox_memory
            WHERE box_id = ? AND category = ? AND key = ?
        """, (self.box_id, category, key)).fetchone()
        conn.close()
        
        if row:
            return {
                "key": key,
                "category": category,
                "value": json.loads(row[0]),
                "proof_hash": row[1],
                "confidence": row[2],
                "created": row[3],
                "updated": row[4],
                "layer": self.layer_id
            }
        return None
    
    def log_event(self, event_type: str, description: str, context: dict = None):
        """Log episodic memory."""
        conn = sqlite3.connect(self.db_path)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT INTO episodic_log (box_id, event_type, description, context, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (self.box_id, event_type, description, 
              json.dumps(context) if context else None, now))
        conn.commit()
        conn.close()


class ThinkCommons(MemoryLayer):
    """L3: Governed collective intelligence shared across all agents."""
    
    def __init__(self, db_path: str):
        super().__init__("THINK COMMONS", 3)
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS commons_knowledge (
                id TEXT PRIMARY KEY,
                knowledge_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                source_agent TEXT,
                proof TEXT,
                confidence REAL DEFAULT 0.5,
                verification_count INTEGER DEFAULT 0,
                tags TEXT,
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS proofs (
                id TEXT PRIMARY KEY,
                knowledge_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                evidence TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_commons_type ON commons_knowledge(knowledge_type)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_commons_tags ON commons_knowledge(tags)
        """)
        conn.commit()
        conn.close()
    
    def contribute(self, knowledge_type: str, title: str, content: str,
                   source_agent: str, proof: str = None, 
                   confidence: float = 0.5, tags: list = None) -> dict:
        """Contribute knowledge to the commons."""
        conn = sqlite3.connect(self.db_path)
        now = datetime.now(timezone.utc).isoformat()
        knowledge_id = hashlib.sha256(f"{title}{content}".encode()).hexdigest()[:16]
        
        conn.execute("""
            INSERT OR REPLACE INTO commons_knowledge
            (id, knowledge_type, title, content, source_agent, proof, confidence, tags, created, updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 
                COALESCE((SELECT created FROM commons_knowledge WHERE id = ?), ?),
                ?)
        """, (knowledge_id, knowledge_type, title, content, source_agent,
              proof, confidence, json.dumps(tags or []), knowledge_id, now, now))
        
        if proof:
            proof_id = hashlib.sha256(f"{knowledge_id}{proof}{source_agent}".encode()).hexdigest()[:16]
            conn.execute("""
                INSERT OR IGNORE INTO proofs (id, knowledge_id, agent_id, evidence, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (proof_id, knowledge_id, source_agent, proof, now))
        
        conn.commit()
        conn.close()
        return {"contributed": knowledge_id, "layer": self.layer_id}
    
    def query(self, knowledge_type: str = None, tags: list = None, 
              min_confidence: float = 0.0, limit: int = 20) -> list:
        """Query the commons."""
        conn = sqlite3.connect(self.db_path)
        query = "SELECT * FROM commons_knowledge WHERE confidence >= ?"
        params = [min_confidence]
        
        if knowledge_type:
            query += " AND knowledge_type = ?"
            params.append(knowledge_type)
        
        if tags:
            for tag in tags:
                query += " AND tags LIKE ?"
                params.append(f"%{tag}%")
        
        query += " ORDER BY confidence DESC, verification_count DESC LIMIT ?"
        params.append(limit)
        
        rows = conn.execute(query, params).fetchall()
        conn.close()
        
        return [{
            "id": r[0],
            "type": r[1],
            "title": r[2],
            "content": r[3][:200],
            "confidence": r[5]
        } for r in rows]


class MemoryOrchestrator:
    """Orchestrates all memory layers for KUDBEE."""
    
    def __init__(self, box_id: str = "kudbee-main"):
        os.makedirs(BASE_DIR, exist_ok=True)
        
        self.working = WorkingMemory()
        self.cache = ElasticCache(DB_PATH)
        self.thinkbox = ThinkBoxMemory(box_id, DB_PATH)
        self.commons = ThinkCommons(DB_PATH)
        self.box_id = box_id
    
    def learn(self, category: str, key: str, value: Any, 
              proof: str = None, confidence: float = 0.5,
              share: bool = False):
        """Store knowledge across layers."""
        # L1: Cache
        self.cache.store(f"{category}/{key}", value)
        
        # L2: Think Box memory
        self.thinkbox.store(category, key, value, proof, confidence)
        
        # L3: Share to commons if requested
        if share:
            self.commons.contribute(
                knowledge_type=category,
                title=key,
                content=json.dumps(value),
                source_agent=self.box_id,
                proof=proof,
                confidence=confidence,
                tags=[category, self.box_id]
            )
        
        return {"stored": f"{category}/{key}", "shared": share}
    
    def recall(self, category: str, key: str) -> dict:
        """Retrieve knowledge from the fastest available layer."""
        # Try L1 cache first
        cached = self.cache.retrieve(f"{category}/{key}")
        if cached:
            return cached
        
        # Try L2 think box memory
        memory = self.thinkbox.retrieve(category, key)
        if memory:
            # Promote to L1 cache
            self.cache.store(f"{category}/{key}", memory["value"])
            return memory
        
        return None
    
    def get_context_package(self, task: str) -> dict:
        """Build a context package for the agent."""
        hot_keys = self.cache.get_hot_keys(min_access=2)
        
        context = {
            "task": task,
            "hot_context": [],
            "commons_knowledge": []
        }
        
        # Add hot context
        for hk in hot_keys[:10]:
            cached = self.cache.retrieve(hk["key"])
            if cached:
                context["hot_context"].append(cached)
        
        # Query commons for relevant knowledge
        commons = self.commons.query(limit=10)
        context["commons_knowledge"] = commons
        
        return context


# Global orchestrator
_orchestrator = None

def get_orchestrator(box_id: str = "kudbee-main") -> MemoryOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MemoryOrchestrator(box_id)
    return _orchestrator


if __name__ == "__main__":
    mem = get_orchestrator()
    
    # Store what we learned today
    mem.learn(
        "infrastructure", 
        "ssh-key-injection",
        {
            "fact": "UpCloud servers are publickey-only SSH by default",
            "gotcha": "New agent keys must be injected at creation or via emergency console",
            "recovery": "Use UpCloud web console → Server → Console → add SSH key"
        },
        proof="Verified by deploying 3 servers over 15 hours",
        confidence=0.95,
        share=True
    )
    
    mem.learn(
        "infrastructure",
        "upcloud-stop-api",
        {
            "correct_format": {"stop_server": {"stop_type": "hard", "timeout": "60"}},
            "wrong_formats": ["{'stop_type': 'hard'}", "{'server': {...}}"],
            "error": "UNKNOWN_ATTRIBUTE for wrong key"
        },
        proof="Tested multiple stop attempts, verified against official docs",
        confidence=0.99,
        share=True
    )
    
    print("Memory system initialized")
    print(f"Hot keys: {len(mem.cache.get_hot_keys(min_access=1))}")
    print(f"Commons entries: {len(mem.commons.query())}")
