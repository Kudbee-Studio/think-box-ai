#!/usr/bin/env python3
"""KUDBEE Quality Control & Fault Tolerance System

Features:
1. Multi-attempt generation with quality scoring
2. Automatic retry on failure
3. Health checks for all services
4. Auto-restart failed services
5. Quality metrics tracking
6. Fallback model selection
"""

import os
import json
import time
import subprocess
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Callable

BASE_DIR = "/opt/kudbee"
DB_PATH = f"{BASE_DIR}/quality.db"
LOG_PATH = f"{BASE_DIR}/logs/quality.log"

# Ensure directories exist
os.makedirs(f"{BASE_DIR}/logs", exist_ok=True)


class QualityScorer:
    """Scores generated audio quality."""
    
    @staticmethod
    def score_audio(file_path: str) -> dict:
        """Analyze audio file and return quality metrics."""
        try:
            # Get audio info with ffprobe
            result = subprocess.run([
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_format", "-show_streams", file_path
            ], capture_output=True, text=True, timeout=30)
            
            info = json.loads(result.stdout)
            streams = info.get("streams", [])
            fmt = info.get("format", {})
            
            if not streams:
                return {"score": 0, "error": "No audio streams"}
            
            audio_stream = streams[0]
            duration = float(fmt.get("duration", 0))
            bit_rate = int(fmt.get("bit_rate", 0))
            sample_rate = int(audio_stream.get("sample_rate", 0))
            channels = int(audio_stream.get("channels", 0))
            
            # Score based on technical quality metrics
            score = 0.0
            metrics = {}
            
            # Duration score (longer = more content)
            if duration > 30:
                score += 0.3
                metrics["duration"] = "good"
            elif duration > 10:
                score += 0.2
                metrics["duration"] = "medium"
            else:
                score += 0.1
                metrics["duration"] = "short"
            
            # Bitrate score (higher = better quality)
            if bit_rate > 250000:
                score += 0.3
                metrics["bitrate"] = "high"
            elif bit_rate > 128000:
                score += 0.2
                metrics["bitrate"] = "medium"
            else:
                score += 0.1
                metrics["bitrate"] = "low"
            
            # Sample rate score
            if sample_rate >= 44100:
                score += 0.2
                metrics["sample_rate"] = "cd_quality"
            else:
                score += 0.1
                metrics["sample_rate"] = "low"
            
            # Channel score (stereo preferred)
            if channels >= 2:
                score += 0.2
                metrics["channels"] = "stereo"
            else:
                score += 0.1
                metrics["channels"] = "mono"
            
            return {
                "score": round(score, 2),
                "duration": duration,
                "bit_rate": bit_rate,
                "sample_rate": sample_rate,
                "channels": channels,
                "metrics": metrics,
                "file": file_path
            }
        except Exception as e:
            return {"score": 0, "error": str(e)}


class FaultTolerantGenerator:
    """Generates music with automatic retry and fallback."""
    
    def __init__(self):
        self.scorer = QualityScorer()
        self.max_retries = 3
        self.min_quality_score = 0.6
        self.generation_log = []
    
    def generate_with_retry(self, generate_fn: Callable, *args, **kwargs) -> Optional[str]:
        """Generate with automatic retry on failure."""
        best_result = None
        best_score = 0
        
        for attempt in range(1, self.max_retries + 1):
            try:
                print(f"  Attempt {attempt}/{self.max_retries}...")
                result = generate_fn(*args, **kwargs)
                
                if result and os.path.exists(result):
                    # Score the result
                    score = self.scorer.score_audio(result)
                    print(f"  Quality score: {score['score']}/1.0")
                    
                    if score["score"] > best_score:
                        best_score = score["score"]
                        best_result = result
                    
                    # If quality is good enough, stop
                    if score["score"] >= self.min_quality_score:
                        return result
                    
                    print(f"  Quality below threshold ({self.min_quality_score}), retrying...")
                
            except Exception as e:
                print(f"  Attempt {attempt} failed: {e}")
                time.sleep(2 ** attempt)  # Exponential backoff
        
        return best_result
    
    def generate_multiple(self, generate_fn: Callable, count: int = 3, **kwargs) -> list:
        """Generate multiple versions and return all scored results."""
        results = []
        
        for i in range(count):
            print(f"Generating version {i+1}/{count}...")
            result = generate_fn(**kwargs)
            
            if result and os.path.exists(result):
                score = self.scorer.score_audio(result)
                results.append({
                    "file": result,
                    "score": score["score"],
                    "metrics": score
                })
        
        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results


class HealthChecker:
    """Monitors service health and auto-restarts failed services."""
    
    SERVICES = [
        {"name": "ollama", "port": 11434, "check_url": "/api/tags"},
        {"name": "nginx", "port": 80, "check_url": "/"},
        {"name": "acestep", "port": 8000, "check_url": "/docs"},
    ]
    
    def __init__(self):
        self.status = {}
    
    def check_service(self, service: dict) -> dict:
        """Check if a service is healthy."""
        import urllib.request
        
        url = f"http://localhost:{service['port']}{service['check_url']}"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                return {
                    "name": service["name"],
                    "status": "healthy",
                    "port": service["port"],
                    "http_code": resp.status
                }
        except Exception as e:
            return {
                "name": service["name"],
                "status": "unhealthy",
                "port": service["port"],
                "error": str(e)
            }
    
    def check_all(self) -> list:
        """Check all services."""
        results = []
        for service in self.SERVICES:
            result = self.check_service(service)
            self.status[result["name"]] = result
            results.append(result)
        return results
    
    def restart_service(self, service_name: str) -> bool:
        """Attempt to restart a failed service."""
        try:
            subprocess.run(
                ["systemctl", "restart", service_name],
                capture_output=True, timeout=30
            )
            time.sleep(5)
            return True
        except Exception as e:
            print(f"Failed to restart {service_name}: {e}")
            return False
    
    def auto_heal(self) -> dict:
        """Check all services and restart unhealthy ones."""
        results = {}
        for service in self.check_all():
            if service["status"] == "unhealthy":
                print(f"Service {service['name']} is unhealthy, restarting...")
                restarted = self.restart_service(service["name"])
                results[service["name"]] = {
                    "action": "restarted" if restarted else "restart_failed",
                    "original_status": service
                }
            else:
                results[service["name"]] = {"action": "none", "status": "healthy"}
        return results


class QualityDatabase:
    """Tracks generation quality over time."""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                prompt TEXT,
                model TEXT,
                output_file TEXT,
                quality_score REAL,
                duration REAL,
                attempt_count INTEGER,
                success BOOLEAN,
                error TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS service_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                service_name TEXT,
                status TEXT,
                response_time REAL
            )
        """)
        conn.commit()
        conn.close()
    
    def log_generation(self, prompt: str, model: str, output_file: str,
                       quality_score: float, duration: float,
                       attempt_count: int, success: bool, error: str = None):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            INSERT INTO generations 
            (timestamp, prompt, model, output_file, quality_score, duration, attempt_count, success, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (datetime.now(timezone.utc).isoformat(), prompt, model, output_file,
              quality_score, duration, attempt_count, success, error))
        conn.commit()
        conn.close()
    
    def get_average_quality(self, model: str = None, limit: int = 100) -> float:
        conn = sqlite3.connect(self.db_path)
        query = "SELECT AVG(quality_score) FROM generations WHERE success = 1"
        params = []
        if model:
            query += " AND model = ?"
            params.append(model)
        query += f" ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        row = conn.execute(query, params).fetchone()
        conn.close()
        return row[0] if row and row[0] else 0.0
    
    def get_failure_rate(self, model: str = None, limit: int = 100) -> float:
        conn = sqlite3.connect(self.db_path)
        query = """
            SELECT 
                CAST(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) 
            FROM generations 
            WHERE 1=1
        """
        params = []
        if model:
            query += " AND model = ?"
            params.append(model)
        
        row = conn.execute(query, params).fetchone()
        conn.close()
        return row[0] if row and row[0] else 0.0


# Global instances
generator = FaultTolerantGenerator()
health_checker = HealthChecker()
quality_db = QualityDatabase()


if __name__ == "__main__":
    print("=== KUDBEE Quality Control System ===")
    
    # Check service health
    print("\n--- Service Health ---")
    for service in health_checker.check_all():
        status_icon = "✓" if service["status"] == "healthy" else "✗"
        print(f"  {status_icon} {service['name']}:{service['port']} - {service['status']}")
    
    # Auto-heal unhealthy services
    print("\n--- Auto-Healing ---")
    heal_results = health_checker.auto_heal()
    for name, result in heal_results.items():
        if result["action"] != "none":
            print(f"  {name}: {result['action']}")
    
    # Quality stats
    print("\n--- Quality Stats ---")
    avg_quality = quality_db.get_average_quality()
    failure_rate = quality_db.get_failure_rate()
    print(f"  Average quality: {avg_quality:.2f}/1.0")
    print(f"  Failure rate: {failure_rate:.1%}")
