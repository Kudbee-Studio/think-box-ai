"""Advanced Solana DeFi protocols — staking, bonding, governance, and gamification."""

from __future__ import annotations

import hashlib
import json
import random
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path("data/solana_protocols.db")
DB_LOCK = threading.Lock()


def _get_db() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS stakes (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            mint TEXT NOT NULL,
            amount INTEGER NOT NULL,
            apy REAL DEFAULT 0.05,
            lock_days INTEGER DEFAULT 30,
            nft_boost REAL DEFAULT 1.0,
            rewards_earned REAL DEFAULT 0.0,
            staked_at TEXT NOT NULL,
            unlocks_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bonding_launches (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            symbol TEXT NOT NULL,
            mint TEXT UNIQUE,
            curve_type TEXT DEFAULT 'linear',
            initial_price REAL DEFAULT 0.0001,
            current_supply INTEGER DEFAULT 0,
            target_supply INTEGER DEFAULT 1000000,
            raised_sol REAL DEFAULT 0.0,
            creator TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS governance_proposals (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            creator TEXT NOT NULL,
            votes_for INTEGER DEFAULT 0,
            votes_against INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL,
            ends_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS achievements (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            requirement_type TEXT,
            requirement_value INTEGER,
            reward_type TEXT,
            reward_value REAL DEFAULT 0.0
        );
        CREATE TABLE IF NULL EXISTS user_achievements (
            user TEXT NOT NULL,
            achievement_id TEXT NOT NULL,
            earned_at TEXT NOT NULL,
            PRIMARY KEY (user, achievement_id)
        );
        CREATE TABLE IF NOT EXISTS referrals (
            id TEXT PRIMARY KEY,
            referrer TEXT NOT NULL,
            referee TEXT UNIQUE NOT NULL,
            fee_earned REAL DEFAULT 0.0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS nft_stakes (
            id TEXT PRIMARY KEY,
            owner TEXT NOT NULL,
            mint TEXT NOT NULL,
            collection TEXT,
            staked_at TEXT NOT NULL,
            rewards_earned REAL DEFAULT 0.0
        );
    """)
    conn.commit()
    return conn


def _generate_id(prefix: str) -> str:
    return f"{prefix}_{hashlib.sha256(f'{time.time()}{random.random()}'.encode()).hexdigest()[:12]}"


@dataclass
class StakeInfo:
    id: str
    owner: str
    mint: str
    amount: int
    apy: float
    lock_days: int
    nft_boost: float
    rewards_earned: float
    staked_at: str
    unlocks_at: str

    @property
    def daily_reward(self) -> float:
        return self.amount * self.apy * self.nft_boost / 365

    @property
    def is_unlocked(self) -> bool:
        return datetime.now(timezone.utc).isoformat() >= self.unlocks_at


class StakingManager:
    def stake(self, owner: str, mint: str, amount: int, lock_days: int = 30, nft_boost: float = 1.0) -> dict[str, Any]:
        base_apy = 0.05
        lock_multiplier = min(lock_days / 30, 4.0)
        apy = base_apy * lock_multiplier * nft_boost
        now = datetime.now(timezone.utc)
        unlock = now.replace(day=now.day + lock_days)

        stake_info = StakeInfo(
            id=_generate_id("stake"),
            owner=owner,
            mint=mint,
            amount=amount,
            apy=apy,
            lock_days=lock_days,
            nft_boost=nft_boost,
            rewards_earned=0.0,
            staked_at=now.isoformat(),
            unlocks_at=unlock.isoformat(),
        )

        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """INSERT INTO stakes (id, owner, mint, amount, apy, lock_days, nft_boost, rewards_earned, staked_at, unlocks_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (stake_info.id, owner, mint, amount, apy, lock_days, nft_boost, 0.0, stake_info.staked_at, stake_info.unlocks_at),
            )
            conn.commit()
            conn.close()

        return {"success": True, "stake": stake_info.__dict__}

    def unstake(self, stake_id: str) -> dict[str, Any]:
        with DB_LOCK:
            conn = _get_db()
            row = conn.execute("SELECT * FROM stakes WHERE id=?", (stake_id,)).fetchone()
            if not row:
                conn.close()
                return {"success": False, "error": "Stake not found"}
            conn.execute("DELETE FROM stakes WHERE id=?", (stake_id,))
            conn.commit()
            conn.close()
        return {"success": True, "amount": row[3], "rewards": row[7]}

    def claim_rewards(self, stake_id: str) -> dict[str, Any]:
        with DB_LOCK:
            conn = _get_db()
            row = conn.execute("SELECT * FROM stakes WHERE id=?", (stake_id,)).fetchone()
            if not row:
                conn.close()
                return {"success": False, "error": "Stake not found"}
            rewards = row[7]
            conn.execute("UPDATE stakes SET rewards_earned=0 WHERE id=?", (stake_id,))
            conn.commit()
            conn.close()
        return {"success": True, "rewards": rewards}

    def get_user_stakes(self, owner: str) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = _get_db()
            rows = conn.execute("SELECT * FROM stakes WHERE owner=?", (owner,)).fetchall()
            conn.close()
        return [
            {
                "id": r[0], "owner": r[1], "mint": r[2], "amount": r[3],
                "apy": r[4], "lock_days": r[5], "nft_boost": r[6],
                "rewards_earned": r[7], "staked_at": r[8], "unlocks_at": r[9],
            }
            for r in rows
        ]


class BondingCurveLaunchpad:
    def create_launch(self, name: str, symbol: str, creator: str, curve_type: str = "linear", target_supply: int = 1_000_000) -> dict[str, Any]:
        launch_id = _generate_id("launch")
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """INSERT INTO bonding_launches (id, name, symbol, curve_type, target_supply, creator, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (launch_id, name, symbol, curve_type, target_supply, creator, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            conn.close()
        return {"success": True, "launch_id": launch_id, "name": name, "symbol": symbol}

    def get_launch(self, launch_id: str) -> dict[str, Any] | None:
        with DB_LOCK:
            conn = _get_db()
            row = conn.execute("SELECT * FROM bonding_launches WHERE id=?", (launch_id,)).fetchone()
            conn.close()
        if not row:
            return None
        return {
            "id": r[0], "name": r[1], "symbol": r[2], "mint": r[3],
            "curve_type": r[4], "initial_price": r[5], "current_supply": r[6],
            "target_supply": r[7], "raised_sol": r[8], "creator": r[9],
            "status": r[10], "created_at": r[11],
        }

    def list_launches(self, status_filter: str | None = None) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = _get_db()
            if status_filter:
                rows = conn.execute("SELECT * FROM bonding_launches WHERE status=? ORDER BY created_at DESC", (status_filter,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM bonding_launches ORDER BY created_at DESC").fetchall()
            conn.close()
        return [
            {"id": r[0], "name": r[1], "symbol": r[2], "current_supply": r[6], "raised_sol": r[8], "status": r[10]}
            for r in rows
        ]

    def buy(self, launch_id: str, buyer: str, amount: int) -> dict[str, Any]:
        import random
        price = 0.0001 * (1 + random.random())
        cost = price * amount
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                "UPDATE bonding_launches SET current_supply = current_supply + ?, raised_sol = raised_sol + ? WHERE id = ?",
                (amount, cost, launch_id),
            )
            conn.commit()
            conn.close()
        return {"success": True, "cost": cost, "price": price, "amount": amount}


class GovernanceManager:
    def create_proposal(self, title: str, description: str, creator: str, duration_days: int = 7) -> dict[str, Any]:
        proposal_id = _generate_id("prop")
        now = datetime.now(timezone.utc)
        ends = now.replace(day=now.day + duration_days)
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                """INSERT INTO governance_proposals (id, title, description, creator, created_at, ends_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (proposal_id, title, description, creator, now.isoformat(), ends.isoformat()),
            )
            conn.commit()
            conn.close()
        return {"success": True, "proposal_id": proposal_id}

    def vote(self, proposal_id: str, voter: str, support: bool) -> dict[str, Any]:
        with DB_LOCK:
            conn = _get_db()
            if support:
                conn.execute("UPDATE governance_proposals SET votes_for = votes_for + 1 WHERE id=?", (proposal_id,))
            else:
                conn.execute("UPDATE governance_proposals SET votes_against = votes_against + 1 WHERE id=?", (proposal_id,))
            conn.commit()
            conn.close()
        return {"success": True, "support": support}

    def list_proposals(self) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = _get_db()
            rows = conn.execute("SELECT * FROM governance_proposals ORDER BY created_at DESC").fetchall()
            conn.close()
        return [
            {"id": r[0], "title": r[1], "creator": r[4], "votes_for": r[5], "votes_against": r[6], "status": r[7]}
            for r in rows
        ]


class AchievementManager:
    DEFAULT_ACHIEVEMENTS = [
        {"name": "First Stake", "description": "Stake your first tokens", "icon": "◎", "requirement_type": "stake_count", "requirement_value": 1, "reward_type": "xp", "reward_value": 100},
        {"name": "Diamond Hands", "description": "Stake for 90+ days", "icon": "💎", "requirement_type": "stake_days", "requirement_value": 90, "reward_type": "xp", "reward_value": 500},
        {"name": "Token Creator", "description": "Launch your first token", "icon": "◈", "requirement_type": "tokens_created", "requirement_value": 1, "reward_type": "xp", "reward_value": 200},
        {"name": "Whale Watcher", "description": "Track 10 wallets", "icon": "🐋", "requirement_type": "wallets_tracked", "requirement_value": 10, "reward_type": "xp", "reward_value": 150},
        {"name": "Governance Voter", "description": "Vote on 5 proposals", "icon": "🗳", "requirement_type": "votes_cast", "requirement_value": 5, "reward_type": "xp", "reward_value": 250},
        {"name": "NFT Collector", "description": "Own 10 NFTs", "icon": "🎨", "requirement_type": "nfts_owned", "requirement_value": 10, "reward_type": "xp", "reward_value": 300},
        {"name": "Referral Master", "description": "Refer 5 users", "icon": "👥", "requirement_type": "referrals", "requirement_value": 5, "reward_type": "fee_share", "reward_value": 0.01},
    ]

    def __init__(self) -> None:
        self._init_achievements()

    def _init_achievements(self) -> None:
        with DB_LOCK:
            conn = _get_db()
            existing = conn.execute("SELECT COUNT(*) FROM achievements").fetchone()[0]
            if existing == 0:
                for a in self.DEFAULT_ACHIEVEMENTS:
                    conn.execute(
                        """INSERT OR IGNORE INTO achievements (id, name, description, icon, requirement_type, requirement_value, reward_type, reward_value)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                        (_generate_id("ach"), a["name"], a["description"], a["icon"], a["requirement_type"], a["requirement_value"], a["reward_type"], a["reward_value"]),
                    )
                conn.commit()
            conn.close()

    def list_achievements(self) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = _get_db()
            rows = conn.execute("SELECT * FROM achievements").fetchall()
            conn.close()
        return [
            {"id": r[0], "name": r[1], "description": r[2], "icon": r[3], "requirement": f"{r[4]}: {r[5]}", "reward": f"{r[6]}: {r[7]}"}
            for r in rows
        ]

    def check_achievements(self, user: str, stats: dict[str, int]) -> list[dict[str, Any]]:
        earned = []
        achievements = self.list_achievements()
        for ach in achievements:
            req_type = ach["requirement"].split(":")[0].strip()
            req_value = int(ach["requirement"].split(":")[1].strip())
            if stats.get(req_type, 0) >= req_value:
                with DB_LOCK:
                    conn = _get_db()
                    existing = conn.execute("SELECT 1 FROM user_achievements WHERE user=? AND achievement_id=?", (user, ach["id"])).fetchone()
                    if not existing:
                        conn.execute("INSERT INTO user_achievements (user, achievement_id, earned_at) VALUES (?, ?, ?)", (user, ach["id"], datetime.now(timezone.utc).isoformat()))
                        conn.commit()
                        earned.append(ach)
                    conn.close()
        return earned


class ReferralManager:
    def register_referral(self, referrer: str, referee: str) -> dict[str, Any]:
        ref_id = _generate_id("ref")
        with DB_LOCK:
            conn = _get_db()
            existing = conn.execute("SELECT 1 FROM referrals WHERE referee=?", (referee,)).fetchone()
            if existing:
                conn.close()
                return {"success": False, "error": "Already referred"}
            conn.execute(
                "INSERT INTO referrals (id, referrer, referee, created_at) VALUES (?, ?, ?, ?)",
                (ref_id, referrer, referee, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            conn.close()
        return {"success": True, "referral_id": ref_id}

    def record_fee(self, referee: str, fee_amount: float) -> None:
        share = fee_amount * 0.1
        with DB_LOCK:
            conn = _get_db()
            conn.execute("UPDATE referrals SET fee_earned = fee_earned + ? WHERE referee=?", (share, referee))
            conn.commit()
            conn.close()

    def get_referrals(self, referrer: str) -> dict[str, Any]:
        with DB_LOCK:
            conn = _get_db()
            rows = conn.execute("SELECT referee, fee_earned FROM referrals WHERE referrer=?", (referrer,)).fetchall()
            conn.close()
        return {"count": len(rows), "total_earned": sum(r[1] for r in rows), "referrals": [{"referee": r[0], "earned": r[1]} for r in rows]}


class NFTStakingManager:
    def stake_nft(self, owner: str, mint: str, collection: str | None = None) -> dict[str, Any]:
        stake_id = _generate_id("nstake")
        with DB_LOCK:
            conn = _get_db()
            conn.execute(
                "INSERT INTO nft_stakes (id, owner, mint, collection, staked_at) VALUES (?, ?, ?, ?, ?)",
                (stake_id, owner, mint, collection, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            conn.close()
        return {"success": True, "stake_id": stake_id}

    def unstake_nft(self, stake_id: str) -> dict[str, Any]:
        with DB_LOCK:
            conn = _get_db()
            row = conn.execute("SELECT * FROM nft_stakes WHERE id=?", (stake_id,)).fetchone()
            if not row:
                conn.close()
                return {"success": False, "error": "Not found"}
            conn.execute("DELETE FROM nft_stakes WHERE id=?", (stake_id,))
            conn.commit()
            conn.close()
        return {"success": True, "mint": row[2], "rewards": r[5] if len(r) > 5 else 0.0}

    def get_staked_nfts(self, owner: str) -> list[dict[str, Any]]:
        with DB_LOCK:
            conn = _get_db()
            rows = conn.execute("SELECT * FROM nft_stakes WHERE owner=?", (owner,)).fetchall()
            conn.close()
        return [{"id": r[0], "mint": r[2], "collection": r[3], "staked_at": r[4], "rewards": r[5]} for r in rows]
