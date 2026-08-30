#!/usr/bin/env python3
"""KUDBEE THINK Token Engine v2

Features:
- Dynamic Weight Decay: Tokens lose value over time without validation
- Token Staking: Lock tokens to authorize higher-tier actions
- Adversarial Red-Teaming: Boxes compete to challenge each other
- Swarm Consensus: Tokens require majority vote for promotion
- Multi-Agent Topology: Specialized sub-routines with domain expertise
"""

import json
import os
import sqlite3
import hashlib
import time
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional


DB_PATH = "/opt/kudbee/memory/think_tokens.db"


class ThinkToken:
    """A single Think Token with full lifecycle."""
    
    def __init__(self, token_id: str, token_type: str, content: str,
                 source_box: str, provenance: str, evidence: str = "",
                 confidence: float = 0.5, stake_required: float = 0.0):
        self.token_id = token_id
        self.token_type = token_type  # knowledge, action, verification, governance
        self.content = content
        self.source_box = source_box
        self.provenance = provenance
        self.evidence = evidence
        self.confidence = confidence  # 0.0 to 1.0
        self.stake_required = stake_required
        self.staked_amount = 0.0
        self.decay_rate = 0.01  # 1% per day without validation
        self.created = datetime.now(timezone.utc).isoformat()
        self.last_validated = self.created
        self.status = "active"  # active, staked, challenged, promoted, decayed
        self.challenges = []
        self.votes = {}
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items()}


class TokenEngine:
    """Core engine for Think Token lifecycle."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS think_tokens (
                token_id TEXT PRIMARY KEY,
                token_type TEXT NOT NULL,
                content TEXT,
                source_box TEXT,
                provenance TEXT,
                evidence TEXT,
                confidence REAL DEFAULT 0.5,
                stake_required REAL DEFAULT 0.0,
                staked_amount REAL DEFAULT 0.0,
                decay_rate REAL DEFAULT 0.01,
                created TEXT NOT NULL,
                last_validated TEXT,
                status TEXT DEFAULT 'active',
                challenges TEXT DEFAULT '[]',
                votes TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stakes (
                stake_id TEXT PRIMARY KEY,
                token_id TEXT NOT NULL,
                box_id TEXT NOT NULL,
                amount REAL NOT NULL,
                action TEXT NOT NULL,
                created TEXT NOT NULL,
                released TEXT,
                FOREIGN KEY (token_id) REFERENCES think_tokens(token_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS red_team_challenges (
                challenge_id TEXT PRIMARY KEY,
                attacker_box TEXT NOT NULL,
                defender_box TEXT NOT NULL,
                token_id TEXT NOT NULL,
                challenge_type TEXT NOT NULL,
                payload TEXT,
                result TEXT,
                winner TEXT,
                created TEXT NOT NULL,
                resolved TEXT,
                FOREIGN KEY (token_id) REFERENCES think_tokens(token_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS swarm_votes (
                vote_id TEXT PRIMARY KEY,
                token_id TEXT NOT NULL,
                box_id TEXT NOT NULL,
                vote TEXT NOT NULL,
                confidence REAL,
                reasoning TEXT,
                created TEXT NOT NULL,
                FOREIGN KEY (token_id) REFERENCES think_tokens(token_id)
            )
        """)
        conn.commit()
        conn.close()
    
    def mint_token(self, token_type: str, content: str, source_box: str,
                   provenance: str, evidence: str = "",
                   confidence: float = 0.5) -> ThinkToken:
        """Mint a new Think Token."""
        token_id = f"THINK-{uuid.uuid4().hex[:8]}"
        
        # Higher-tier tokens require staking
        stake_required = 0.0
        if token_type in ("governance", "code_execution", "knowledge_promotion"):
            stake_required = 10.0  # Minimum stake
        
        token = ThinkToken(
            token_id=token_id,
            token_type=token_type,
            content=content,
            source_box=source_box,
            provenance=provenance,
            evidence=evidence,
            confidence=confidence,
            stake_required=stake_required
        )
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO think_tokens 
            (token_id, token_type, content, source_box, provenance, evidence,
             confidence, stake_required, created, last_validated, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (token.token_id, token.token_type, token.content,
              token.source_box, token.provenance, token.evidence,
              token.confidence, token.stake_required, token.created,
              token.last_validated, token.status))
        conn.commit()
        conn.close()
        
        return token
    
    def apply_decay(self, token_id: str) -> float:
        """Apply time-decay to a token's confidence."""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT confidence, last_validated, decay_rate FROM think_tokens WHERE token_id = ?",
            (token_id,)
        ).fetchone()
        
        if not row:
            conn.close()
            return 0.0
        
        confidence, last_validated_str, decay_rate = row
        last_validated = datetime.fromisoformat(last_validated_str)
        now = datetime.now(timezone.utc)
        days_elapsed = (now - last_validated).total_seconds() / 86400
        
        # Apply exponential decay
        decay_factor = (1 - decay_rate) ** days_elapsed
        new_confidence = confidence * decay_factor
        
        conn.execute("""
            UPDATE think_tokens SET confidence = ? WHERE token_id = ?
        """, (new_confidence, token_id))
        conn.commit()
        conn.close()
        
        return new_confidence
    
    def stake_token(self, token_id: str, box_id: str, amount: float,
                    action: str) -> bool:
        """Stake tokens to authorize an action."""
        conn = sqlite3.connect(self.db_path)
        
        # Check if token exists and is active
        row = conn.execute(
            "SELECT stake_required, status FROM think_tokens WHERE token_id = ?",
            (token_id,)
        ).fetchone()
        
        if not row:
            conn.close()
            return False
        
        stake_required, status = row
        if status != "active":
            conn.close()
            return False
        
        if amount < stake_required:
            conn.close()
            return False
        
        # Create stake record
        stake_id = f"STAKE-{uuid.uuid4().hex[:8]}"
        conn.execute("""
            INSERT INTO stakes (stake_id, token_id, box_id, amount, action, created)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (stake_id, token_id, box_id, amount, action, datetime.now(timezone.utc).isoformat()))
        
        # Update token
        conn.execute("""
            UPDATE think_tokens SET staked_amount = staked_amount + ?, status = 'staked'
            WHERE token_id = ?
        """, (amount, token_id))
        
        conn.commit()
        conn.close()
        
        return True
    
    def challenge_token(self, token_id: str, attacker_box: str,
                       challenge_type: str, payload: str) -> dict:
        """Launch an adversarial challenge against a token."""
        challenge_id = f"CHAL-{uuid.uuid4().hex[:8]}"
        
        conn = sqlite3.connect(self.db_path)
        
        # Get defender info
        row = conn.execute(
            "SELECT source_box, confidence FROM think_tokens WHERE token_id = ?",
            (token_id,)
        ).fetchone()
        
        if not row:
            conn.close()
            return {"error": "Token not found"}
        
        defender_box, current_confidence = row
        
        # Record challenge
        conn.execute("""
            INSERT INTO red_team_challenges 
            (challenge_id, attacker_box, defender_box, token_id, challenge_type, payload, created)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (challenge_id, attacker_box, defender_box, token_id,
              challenge_type, payload, datetime.now(timezone.utc).isoformat()))
        
        conn.commit()
        conn.close()
        
        return {
            "challenge_id": challenge_id,
            "attacker": attacker_box,
            "defender": defender_box,
            "status": "pending",
        }
    
    def resolve_challenge(self, challenge_id: str, winner: str, reasoning: str):
        """Resolve a challenge and adjust token scores."""
        conn = sqlite3.connect(self.db_path)
        
        row = conn.execute(
            "SELECT token_id, attacker_box, defender_box FROM red_team_challenges WHERE challenge_id = ?",
            (challenge_id,)
        ).fetchone()
        
        if not row:
            conn.close()
            return
        
        token_id, attacker, defender = row
        
        # Winner gets confidence boost, loser gets penalty
        if winner == attacker:
            # Challenge succeeded - defender loses confidence
            conn.execute("""
                UPDATE think_tokens SET confidence = MAX(0, confidence - 0.1)
                WHERE token_id = ?
            """, (token_id,))
        else:
            # Challenge failed - token gains confidence
            conn.execute("""
                UPDATE think_tokens SET confidence = MIN(1.0, confidence + 0.05)
                WHERE token_id = ?
            """, (token_id,))
        
        # Record result
        conn.execute("""
            UPDATE red_team_challenges SET result = ?, winner = ?, resolved = ?
            WHERE challenge_id = ?
        """, (reasoning, winner, datetime.now(timezone.utc).isoformat(), challenge_id))
        
        conn.commit()
        conn.close()
    
    def swarm_vote(self, token_id: str, box_id: str, vote: str,
                   confidence: float, reasoning: str):
        """Record a vote from a swarm member."""
        vote_id = f"VOTE-{uuid.uuid4().hex[:8]}"
        
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO swarm_votes (vote_id, token_id, box_id, vote, confidence, reasoning, created)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (vote_id, token_id, box_id, vote, confidence, reasoning,
              datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
    
    def check_swarm_consensus(self, token_id: str, threshold: float = 0.6) -> dict:
        """Check if a token has achieved swarm consensus."""
        conn = sqlite3.connect(self.db_path)
        
        rows = conn.execute("""
            SELECT vote, confidence FROM swarm_votes WHERE token_id = ?
        """, (token_id,)).fetchall()
        
        if not rows:
            conn.close()
            return {"consensus": False, "reason": "No votes cast"}
        
        approve_count = sum(1 for r in rows if r[0] == "approve")
        total = len(rows)
        approval_rate = approve_count / total
        
        # Weighted by confidence
        weighted_approval = sum(r[1] for r in rows if r[0] == "approve")
        total_weight = sum(r[1] for r in rows)
        weighted_rate = weighted_approval / total_weight if total_weight > 0 else 0
        
        conn.close()
        
        return {
            "consensus": weighted_rate >= threshold,
            "approval_rate": approval_rate,
            "weighted_rate": weighted_rate,
            "total_votes": total,
            "threshold": threshold,
        }
    
    def get_token(self, token_id: str) -> Optional[dict]:
        """Get token by ID."""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT * FROM think_tokens WHERE token_id = ?", (token_id,)
        ).fetchone()
        conn.close()
        
        if not row:
            return None
        
        columns = ["token_id", "token_type", "content", "source_box", "provenance",
                   "evidence", "confidence", "stake_required", "staked_amount",
                   "decay_rate", "created", "last_validated", "status",
                   "challenges", "votes"]
        return dict(zip(columns, row))
    
    def list_tokens(self, status: str = None) -> list:
        """List all tokens, optionally filtered by status."""
        conn = sqlite3.connect(self.db_path)
        
        if status:
            rows = conn.execute(
                "SELECT * FROM think_tokens WHERE status = ?", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM think_tokens").fetchall()
        
        conn.close()
        
        columns = ["token_id", "token_type", "content", "source_box", "provenance",
                   "evidence", "confidence", "stake_required", "staked_amount",
                   "decay_rate", "created", "last_validated", "status",
                   "challenges", "votes"]
        
        return [dict(zip(columns, row)) for row in rows]
    
    def get_stats(self) -> dict:
        """Get engine statistics."""
        conn = sqlite3.connect(self.db_path)
        
        total = conn.execute("SELECT COUNT(*) FROM think_tokens").fetchone()[0]
        active = conn.execute("SELECT COUNT(*) FROM think_tokens WHERE status='active'").fetchone()[0]
        staked = conn.execute("SELECT COUNT(*) FROM think_tokens WHERE status='staked'").fetchone()[0]
        challenged = conn.execute("SELECT COUNT(*) FROM red_team_challenges").fetchone()[0]
        votes = conn.execute("SELECT COUNT(*) FROM swarm_votes").fetchone()[0]
        
        avg_confidence = conn.execute(
            "SELECT AVG(confidence) FROM think_tokens"
        ).fetchone()[0] or 0
        
        conn.close()
        
        return {
            "total_tokens": total,
            "active": active,
            "staked": staked,
            "challenges": challenged,
            "votes": votes,
            "avg_confidence": round(avg_confidence, 3),
        }


if __name__ == "__main__":
    engine = TokenEngine()
    print("THINK Token Engine initialized!")
    print(f"Stats: {engine.get_stats()}")
