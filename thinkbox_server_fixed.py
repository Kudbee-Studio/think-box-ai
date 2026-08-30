#!/usr/bin/env python3
"""KUDBEE Think Box Server"""

import json
import os
import uuid
import time
import sqlite3
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime, timezone

DB_PATH = "/opt/kudbee/memory/kudbee.db"
OLLAMA_URL = "http://localhost:11434"

class ThinkBox:
    def __init__(self, box_type, task, box_id=None):
        self.box_id = box_id or f"{box_type}-{uuid.uuid4().hex[:8]}"
        self.box_type = box_type
        self.task = task
        self.status = "initializing"
        self.created = datetime.now(timezone.utc).isoformat()
        self.completed = None
        self.result = None
    
    def to_dict(self):
        return {
            "box_id": self.box_id,
            "type": self.box_type,
            "task": self.task,
            "status": self.status,
            "created": self.created,
            "completed": self.completed,
            "result": self.result,
        }


class ThinkBoxManager:
    def __init__(self):
        self.boxes = {}
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS think_boxes (
                box_id TEXT PRIMARY KEY,
                box_type TEXT NOT NULL,
                task TEXT,
                status TEXT DEFAULT 'active',
                created TEXT NOT NULL,
                completed TEXT,
                result TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def create_box(self, box_type, task):
        box = ThinkBox(box_type, task)
        self.boxes[box.box_id] = box
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO think_boxes (box_id, box_type, task, status, created)
            VALUES (?, ?, ?, ?, ?)
        """, (box.box_id, box.box_type, task, box.status, box.created))
        conn.commit()
        conn.close()
        
        box.status = "running"
        self._run_box(box)
        
        return box
    
    def _run_box(self, box):
        try:
            if box.box_type == "director":
                box.result = self._run_director(box.task)
            elif box.box_type == "music":
                box.result = self._run_music(box.task)
            elif box.box_type == "voice":
                box.result = self._run_voice(box.task)
            elif box.box_type == "trend-researcher":
                box.result = self._run_trend_research(box.task)
            elif box.box_type == "image-gen":
                box.result = self._run_image_gen(box.task)
            elif box.box_type == "video-gen":
                box.result = self._run_video_gen(box.task)
            elif box.box_type == "script-writer":
                box.result = self._run_script_writer(box.task)
            else:
                box.result = {"message": f"Generic box: {box.task}"}
        except Exception as e:
            box.result = {"error": str(e)}
        
        box.status = "completed"
        box.completed = datetime.now(timezone.utc).isoformat()
        
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            UPDATE think_boxes SET status=?, completed=?, result=? WHERE box_id=?
        """, (box.status, box.completed, json.dumps(box.result), box.box_id))
        conn.commit()
        conn.close()
    
    def _run_director(self, task):
        resp = requests.post(f"{OLLAMA_URL}/api/generate", json={
            "model": "gpt-oss:20b",
            "prompt": f"You are a film director. Create a detailed storyboard for: {task}. Include 8 scenes with camera shots, dialogue, and mood descriptions.",
            "stream": False
        }, timeout=180)
        script = resp.json().get("response", "")
        return {
            "type": "storyboard",
            "content": script[:1000],
            "model": "gpt-oss:20b",
            "scenes": 8,
        }
    
    def _run_script_writer(self, task):
        resp = requests.post(f"{OLLAMA_URL}/api/generate", json={
            "model": "gpt-oss:120b",
            "prompt": f"Write a complete screenplay for: {task}. Include scene headings, character names, dialogue, and action lines.",
            "stream": False
        }, timeout=300)
        script = resp.json().get("response", "")
        return {
            "type": "screenplay",
            "content": script[:2000],
            "model": "gpt-oss:120b",
            "pages": len(script) // 500,
        }
    
    def _run_music(self, task):
        return {"status": "ready", "engine": "ACE-Step 1.5 XL", "task": task}
    
    def _run_voice(self, task):
        return {"status": "ready", "engine": "Coqui TTS", "task": task}
    
    def _run_trend_research(self, task):
        products = [
            {"name": "Perfume Fragrance", "demand": 94, "margin": 68, "score": 89},
            {"name": "Vitamin C Serum", "demand": 88, "margin": 72, "score": 85},
            {"name": "Portable Sealer", "demand": 82, "margin": 78, "score": 82},
            {"name": "Wireless Fan", "demand": 79, "margin": 65, "score": 76},
        ]
        products.sort(key=lambda x: x["score"], reverse=True)
        return {
            "products": products[:3],
            "recommendation": products[0],
        }
    
    def _run_image_gen(self, task):
        return {"status": "ready", "engine": "FLUX.1-dev", "task": task}
    
    def _run_video_gen(self, task):
        return {"status": "ready", "engine": "LTX-2.3", "task": task}
    
    def list_boxes(self):
        return [box.to_dict() for box in self.boxes.values()]


manager = ThinkBoxManager()


class RequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/boxes":
            boxes = manager.list_boxes()
            self.send_json(200, {"boxes": boxes})
        
        elif parsed.path == "/status":
            conn = sqlite3.connect(DB_PATH)
            total = conn.execute("SELECT COUNT(*) FROM think_boxes").fetchone()[0]
            active = conn.execute("SELECT COUNT(*) FROM think_boxes WHERE status != 'completed'").fetchone()[0]
            completed = conn.execute("SELECT COUNT(*) FROM think_boxes WHERE status = 'completed'").fetchone()[0]
            conn.close()
            self.send_json(200, {"total_boxes": total, "active": active, "completed": completed})
        
        else:
            self.send_json(404, {"error": "not found"})
    
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        data = json.loads(body) if body else {}
        
        if self.path == "/create":
            box_type = data.get("type", "generic")
            task = data.get("task", "")
            box = manager.create_box(box_type, task)
            self.send_json(200, box.to_dict())
        
        elif self.path == "/research":
            box = manager.create_box("trend-researcher", data.get("query", ""))
            self.send_json(200, box.to_dict())
        
        elif self.path == "/script":
            box = manager.create_box("script-writer", data.get("brief", ""))
            self.send_json(200, box.to_dict())
        
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


if __name__ == "__main__":
    port = int(os.environ.get("THINKBOX_PORT", 9090))
    server = HTTPServer(("0.0.0.0", port), RequestHandler)
    print(f"KUDBEE Think Box Server running on port {port}")
    server.serve_forever()
