"""KUDBEE Production Management System

Manages cinematic productions with:
- Storyboard creation
- Scene management
- Cut tracking
- Status dashboard
- Checkpoint/resume
- Quality gates
"""

from __future__ import annotations

import json
import os
import time
import uuid
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


# ═══════════════════════════════════════════════════════════════════════════
# TYPES
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class StoryboardFrame:
    """A single storyboard frame."""
    frame_id: int
    description: str
    camera_shot: str  # close-up, medium, wide, pov, etc.
    camera_movement: str  # static, pan, tilt, dolly, zoom
    mood: str
    notes: str = ""
    reference_image: str = ""


@dataclass
class Scene:
    """A production scene."""
    scene_id: int
    title: str
    description: str
    location: str
    characters: list[str]
    duration_seconds: float
    storyboard: list[StoryboardFrame] = field(default_factory=list)
    cuts: list[Cut] = field(default_factory=list)
    status: str = "pending"  # pending, storyboarding, generating, reviewing, approved, failed
    assets: dict[str, list[str]] = field(default_factory=dict)
    evaluation: dict[str, Any] = field(default_factory=dict)
    checkpoint_path: str = ""


@dataclass
class Cut:
    """A cut within a scene."""
    cut_id: int
    description: str
    duration: float
    asset_path: str = ""
    status: str = "pending"
    quality_score: float = 0.0
    retries: int = 0


@dataclass
class ProductionManifest:
    """Complete production state."""
    production_id: str
    title: str
    logline: str
    target_duration: float
    status: str = "pending"
    scenes: list[Scene] = field(default_factory=dict)
    characters: dict[str, dict[str, str]] = field(default_factory=dict)
    locations: dict[str, str] = field(default_factory=dict)
    soundtrack: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ═══════════════════════════════════════════════════════════════════════════
# PRODUCTION MANAGER
# ═══════════════════════════════════════════════════════════════════════════

class ProductionManager:
    """Manages cinematic productions with checkpoint/resume."""
    
    def __init__(self, work_dir: str = "/opt/kudbee/production"):
        self.work_dir = work_dir
        self.db_path = f"{work_dir}/production.db"
        os.makedirs(work_dir, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS productions (
                production_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                logline TEXT,
                target_duration REAL,
                status TEXT DEFAULT 'pending',
                manifest_json TEXT,
                created TEXT NOT NULL,
                updated TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                production_id TEXT NOT NULL,
                scene_id INTEGER NOT NULL,
                title TEXT,
                description TEXT,
                location TEXT,
                duration REAL,
                status TEXT DEFAULT 'pending',
                storyboard_json TEXT,
                cuts_json TEXT,
                assets_json TEXT,
                evaluation_json TEXT,
                checkpoint_path TEXT,
                PRIMARY KEY (production_id, scene_id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                production_id TEXT NOT NULL,
                scene_id INTEGER NOT NULL,
                checkpoint_type TEXT,
                data_json TEXT,
                created TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()
    
    def create_production(self, title: str, logline: str, target_duration: float = 90.0) -> ProductionManifest:
        """Create a new production."""
        manifest = ProductionManifest(
            production_id=str(uuid.uuid4())[:12],
            title=title,
            logline=logline,
            target_duration=target_duration,
        )
        self._save_manifest(manifest)
        return manifest
    
    def create_storyboard(self, production_id: str, scenes_data: list[dict]) -> ProductionManifest:
        """Create storyboard with scenes and shots."""
        manifest = self._load_manifest(production_id)
        if not manifest:
            raise ValueError(f"Production {production_id} not found")
        
        for i, scene_data in enumerate(scenes_data, 1):
            scene = Scene(
                scene_id=i,
                title=scene_data.get("title", f"Scene {i}"),
                description=scene_data.get("description", ""),
                location=scene_data.get("location", "unknown"),
                characters=scene_data.get("characters", []),
                duration_seconds=scene_data.get("duration", 8.0),
                status="pending",
            )
            
            # Create storyboard frames
            for j, shot in enumerate(scene_data.get("shots", []), 1):
                frame = StoryboardFrame(
                    frame_id=j,
                    description=shot.get("description", ""),
                    camera_shot=shot.get("camera_shot", "medium"),
                    camera_movement=shot.get("movement", "static"),
                    mood=shot.get("mood", "neutral"),
                    notes=shot.get("notes", ""),
                )
                scene.storyboard.append(frame)
            
            # Create cuts from frames
            for j, frame in enumerate(scene.storyboard, 1):
                cut = Cut(
                    cut_id=j,
                    description=frame.description,
                    duration=scene.duration_seconds / max(len(scene.storyboard), 1),
                )
                scene.cuts.append(cut)
            
            manifest.scenes.append(scene)
        
        self._save_manifest(manifest)
        return manifest
    
    def get_status(self, production_id: str) -> dict[str, Any]:
        """Get production status for dashboard."""
        manifest = self._load_manifest(production_id)
        if not manifest:
            return {"error": "Production not found"}
        
        scene_statuses = {}
        total_duration = 0
        completed_duration = 0
        
        for scene in manifest.scenes:
            scene_statuses[scene.scene_id] = {
                "title": scene.title,
                "status": scene.status,
                "duration": scene.duration_seconds,
                "cuts_total": len(scene.cuts),
                "cuts_completed": sum(1 for c in scene.cuts if c.status == "approved"),
                "evaluation": scene.evaluation,
            }
            total_duration += scene.duration_seconds
            if scene.status == "approved":
                completed_duration += scene.duration_seconds
        
        return {
            "production_id": production_id,
            "title": manifest.title,
            "status": manifest.status,
            "target_duration": manifest.target_duration,
            "total_scenes": len(manifest.scenes),
            "scenes_completed": sum(1 for s in manifest.scenes if s.status == "approved"),
            "duration_planned": total_duration,
            "duration_completed": completed_duration,
            "progress": completed_duration / manifest.target_duration if manifest.target_duration > 0 else 0,
            "scenes": scene_statuses,
            "characters": manifest.characters,
            "locations": manifest.locations,
            "updated_at": manifest.updated_at,
        }
    
    def save_checkpoint(self, production_id: str, scene_id: int, checkpoint_type: str, data: dict) -> str:
        """Save a checkpoint for resumability."""
        checkpoint_id = str(uuid.uuid4())[:12]
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO checkpoints (checkpoint_id, production_id, scene_id, checkpoint_type, data_json, created)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (checkpoint_id, production_id, scene_id, checkpoint_type, json.dumps(data),
              datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
        return checkpoint_id
    
    def get_latest_checkpoint(self, production_id: str, scene_id: int) -> Optional[dict]:
        """Get latest checkpoint for a scene."""
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("""
            SELECT data_json FROM checkpoints
            WHERE production_id = ? AND scene_id = ?
            ORDER BY created DESC LIMIT 1
        """, (production_id, scene_id)).fetchone()
        conn.close()
        return json.loads(row[0]) if row else None
    
    def _save_manifest(self, manifest: ProductionManifest) -> None:
        manifest.updated_at = datetime.now(timezone.utc).isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT OR REPLACE INTO productions
            (production_id, title, logline, target_duration, status, manifest_json, created, updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            manifest.production_id, manifest.title, manifest.logline,
            manifest.target_duration, manifest.status,
            json.dumps(manifest.__dict__, default=str),
            manifest.created_at, manifest.updated_at
        ))
        
        for scene in manifest.scenes:
            conn.execute("""
                INSERT OR REPLACE INTO scenes
                (production_id, scene_id, title, description, location, duration, status,
                 storyboard_json, cuts_json, assets_json, evaluation_json, checkpoint_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                manifest.production_id, scene.scene_id, scene.title, scene.description,
                scene.location, scene.duration_seconds, scene.status,
                json.dumps([f.__dict__ for f in scene.storyboard]),
                json.dumps([c.__dict__ for c in scene.cuts]),
                json.dumps(scene.assets),
                json.dumps(scene.evaluation),
                scene.checkpoint_path
            ))
        
        conn.commit()
        conn.close()
    
    def _load_manifest(self, production_id: str) -> Optional[ProductionManifest]:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT manifest_json FROM productions WHERE production_id = ?",
            (production_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        data = json.loads(row[0])
        return ProductionManifest(**{k: v for k, v in data.items() if k in ProductionManifest.__dataclass_fields__})


# ═══════════════════════════════════════════════════════════════════════════
# STATUS DASHBOARD (CLI)
# ═══════════════════════════════════════════════════════════════════════════

def print_status(production_id: str):
    """Print production status to terminal."""
    pm = ProductionManager()
    status = pm.get_status(production_id)
    
    if "error" in status:
        print(f"ERROR: {status['error']}")
        return
    
    print("=" * 70)
    print(f"  KUDBEE Production Status")
    print("=" * 70)
    print(f"  Title:    {status['title']}")
    print(f"  ID:       {status['production_id']}")
    print(f"  Status:   {status['status']}")
    print(f"  Scenes:   {status['scenes_completed']}/{status['total_scenes']}")
    print(f"  Duration: {status['duration_completed']:.0f}/{status['target_duration']:.0f}s")
    print(f"  Progress: {status['progress']*100:.0f}%")
    print("=" * 70)
    
    for sid, scene in sorted(status['scenes'].items()):
        icon = {
            "pending": "⏳",
            "storyboarding": "📋",
            "generating": "🎬",
            "reviewing": "👁️",
            "approved": "✅",
            "failed": "❌",
        }.get(scene['status'], "?")
        
        cuts = f"{scene['cuts_completed']}/{scene['cuts_total']} cuts"
        print(f"  {icon} Scene {sid}: {scene['title']:<30} {scene['status']:<12} {cuts}")
    
    print("=" * 70)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 production.py <production_id> [create|status|storyboard]")
        sys.exit(1)
    
    production_id = sys.argv[1]
    action = sys.argv[2] if len(sys.argv) > 2 else "status"
    
    if action == "status":
        print_status(production_id)
    elif action == "create":
        pm = ProductionManager()
        manifest = pm.create_production(
            title="KUDBEE: Origin",
            logline="A normal man discovers his brother's hidden life after a violent encounter.",
            target_duration=90.0,
        )
        print(f"Created production: {manifest.production_id}")
