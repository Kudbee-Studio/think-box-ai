"""AI Trading Agent system for Solana DeFi."""

from __future__ import annotations

import random
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("data/agents.db")
DB_LOCK = threading.Lock()


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trading_agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            strategy TEXT NOT NULL,
            status TEXT DEFAULT 'paused',
            config TEXT DEFAULT '{}',
            pnl_usd REAL DEFAULT 0.0,
            trades_count INTEGER DEFAULT 0,
            win_rate REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            last_run TEXT
        );
        CREATE TABLE IF NOT EXISTS agent_trades (
            id TEXT PRIMARY KEY,
            agent_id TEXT NOT NULL,
            token_in TEXT NOT NULL,
            token_out TEXT NOT NULL,
            amount_in REAL NOT NULL,
            amount_out REAL NOT NULL,
            pnl_usd REAL DEFAULT 0.0,
            timestamp TEXT NOT NULL,
            FOREIGN KEY (agent_id) REFERENCES trading_agents(id)
        );
    """)
    conn.commit()
    return conn


@dataclass
class AgentTrade:
    agent_id: str
    token_in: str
    token_out: str
    amount_in: float
    amount_out: float
    pnl_usd: float
    timestamp: str


class TradingAgentManager:
    STRATEGIES = {
        "momentum": "Buy tokens with upward price momentum, sell on reversal",
        "mean_reversion": "Buy dip, sell rally based on moving averages",
        "arbitrage": "Exploit price differences across DEXes",
        "snipe": "First-block buying on new token launches",
        "grid": "Place buy/sell orders at regular price intervals",
        "dca": "Dollar-cost average into SOL on a schedule",
    }

    def create_agent(self, name: str, strategy: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        if strategy not in self.STRATEGIES:
            return {"success": False, "error": f"Unknown strategy: {strategy}"}

        agent_id = f"agent_{int(time.time())}{random.randint(1000, 9999)}"
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """INSERT INTO trading_agents (id, name, strategy, config, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (agent_id, name, strategy, json.dumps(config or {}), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            conn.close()

        return {
            "success": True,
            "agent_id": agent_id,
            "name": name,
            "strategy": strategy,
            "description": self.STRATEGIES[strategy],
        }

    def start_agent(self, agent_id: str) -> dict[str, Any]:
        with DB_LOCK:
            conn = _get_db()
            conn.execute("UPDATE trading_agents SET status='active', last_run=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), agent_id))
            conn.commit()
            conn.close()
        return {"success": True, "status": "active"}

    def pause_agent(self, agent_id: str) -> dict[str, Any]:
        with DB_LOCK:
            conn = _get_db()
            conn.execute("UPDATE trading_agents SET status='paused' WHERE id=?", (agent_id,))
            conn.commit()
            conn.close()
        return {"success": True, "status": "paused"}

    def delete_agent(self, agent_id: str) -> dict[str, Any]:
        with DB_LOCK:
            conn = _get_db()
            conn.execute("DELETE FROM agent_trades WHERE agent_id=?", (agent_id,))
            conn.execute("DELETE FROM trading_agents WHERE id=?", (agent_id,))
            conn.commit()
            conn.close()
        return {"success": True}

    def list_agents(self) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = _get_db()
            rows = conn.execute("SELECT id, name, strategy, status, pnl_usd, trades_count, win_rate, created_at FROM trading_agents ORDER BY created_at DESC").fetchall()
            conn.close()
        return [
            {
                "id": r[0], "name": r[1], "strategy": r[2], "status": r[3],
                "pnl_usd": r[4], "trades_count": r[5], "win_rate": r[6], "created_at": r[7],
            }
            for r in rows
        ]

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        with DB_LOCK:
            conn = _get_db()
            row = conn.execute("SELECT * FROM trading_agents WHERE id=?", (agent_id,)).fetchone()
            conn.close()
        if not row:
            return None
        return {
            "id": row[0], "name": row[1], "strategy": row[2], "status": row[3],
            "config": json.loads(row[4]), "pnl_usd": row[5], "trades_count": row[6],
            "win_rate": row[7], "created_at": row[8], "last_run": row[9],
        }

    def simulate_trade(self, agent_id: str) -> dict[str, Any]:
        pnl = random.uniform(-50, 100)
        trade = {
            "agent_id": agent_id,
            "token_in": "SOL",
            "token_out": random.choice(["USDC", "BONK", "WIF", "JUP"]),
            "amount_in": random.uniform(0.1, 5.0),
            "amount_out": random.uniform(10, 500),
            "pnl_usd": pnl,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """INSERT INTO agent_trades (id, agent_id, token_in, token_out, amount_in, amount_out, pnl_usd, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"trade_{int(time.time())}{random.randint(100, 999)}", trade["agent_id"], trade["token_in"], trade["token_out"], trade["amount_in"], trade["amount_out"], trade["pnl_usd"], trade["timestamp"]),
            )
            conn.execute(
                "UPDATE trading_agents SET pnl_usd = pnl_usd + ?, trades_count = trades_count + 1, last_run = ? WHERE id = ?",
                (pnl, trade["timestamp"], agent_id),
            )
            conn.commit()
            conn.close()
        return {"success": True, "trade": trade}


import json
