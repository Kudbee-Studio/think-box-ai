#!/usr/bin/env python3
"""KUDBEE Queue System - Autonomous workflow processor

Drop a .queue.json file into /opt/kudbee/queue/incoming/
The system processes each item using GPT-120B
Results go to /opt/kudbee/queue/done/
"""

import json
import os
import time
import subprocess
import hashlib
import glob
from datetime import datetime
from pathlib import Path

QUEUE_DIR = "/opt/kudbee/queue"
INCOMING = f"{QUEUE_DIR}/incoming"
PROCESSING = f"{QUEUE_DIR}/processing"
DONE = f"{QUEUE_DIR}/done"
FAILED = f"{QUEUE_DIR}/failed"

# Ensure directories exist
for d in [INCOMING, PROCESSING, DONE, FAILED]:
    os.makedirs(d, exist_ok=True)

OLLAMA_URL = "http://localhost:11434"

def think_tokenize(task):
    """Break task into think tokens"""
    return {
        "id": hashlib.md5(task.encode()).hexdigest()[:8],
        "task": task,
        "timestamp": datetime.now().isoformat(),
        "status": "pending",
        "band": {
            "lead": None,
            "drummer": None,
            "bass": None,
            "rhythm": None
        }
    }

def process_with_gpt(task):
    """Process task with GPT-OSS-120B"""
    try:
        result = subprocess.run([
            "curl", "-s", f"{OLLAMA_URL}/api/generate",
            "-d", json.dumps({
                "model": "gpt-oss:120b",
                "prompt": task,
                "stream": False
            })
        ], capture_output=True, text=True, timeout=300)
        return json.loads(result.stdout).get("response", "")
    except Exception as e:
        return f"Error: {e}"

def process_queue():
    """Process all items in the queue"""
    queue_files = glob.glob(f"{INCOMING}/*.queue.json")
    
    for qf in sorted(queue_files):
        print(f"\n📋 Processing: {qf}")
        
        # Move to processing
        processing_path = qf.replace(INCOMING, PROCESSING)
        os.rename(qf, processing_path)
        
        # Load queue
        with open(processing_path) as f:
            queue = json.load(f)
        
        results = []
        for item in queue["items"]:
            print(f"  🔄 {item['task'][:60]}...")
            
            # Think token
            token = think_tokenize(item["task"])
            
            # Process with GPT-120B
            result = process_with_gpt(item["task"])
            token["result"] = result
            token["status"] = "done"
            results.append(token)
            
            print(f"  ✅ Done ({len(result)} chars)")
        
        # Save results
        output = {
            "queue_id": queue.get("id", "unknown"),
            "completed": datetime.now().isoformat(),
            "results": results
        }
        
        done_path = qf.replace(INCOMING, DONE).replace(".queue.json", ".done.json")
        with open(done_path, "w") as f:
            json.dump(output, f, indent=2)
        
        os.remove(processing_path)
        print(f"  📁 Result saved: {done_path}")

def watch_loop():
    """Watch for new queue files"""
    print("👀 Queue watcher started...")
    while True:
        process_queue()
        time.sleep(10)

if __name__ == "__main__":
    watch_loop()
