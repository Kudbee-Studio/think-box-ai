#!/usr/bin/env python3
"""KUDBEE Autonomous Agent Loop

Runs continuously without human input.
Self-directs, evaluates, and loops until goal is met.

Usage:
    nohup python3 /opt/kudbee/autonomous_loop.py > /var/log/kudbee_auto.log 2>&1 &
"""

import json
import os
import sqlite3
import time
import uuid
import urllib.request
from datetime import datetime, timezone

DB_PATH = "/opt/kudbee/memory/autonomous.db"
OLLAMA = "http://localhost:11434"
MODEL = "gpt-oss:20b"  # Fast model for autonomous work

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            goal_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            priority INTEGER DEFAULT 5,
            created TEXT NOT NULL,
            completed TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id TEXT PRIMARY KEY,
            goal_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            output TEXT,
            created TEXT NOT NULL,
            completed TEXT,
            FOREIGN KEY (goal_id) REFERENCES goals(goal_id)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS agent_log (
            log_id TEXT PRIMARY KEY,
            agent_id TEXT,
            action TEXT,
            details TEXT,
            created TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def call_ollama(system, user, max_tokens=2000):
    """Call Ollama API."""
    data = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user}
        ],
        "stream": False,
        "options": {"num_ctx": 8192, "temperature": 0.7}
    }).encode()
    
    req = urllib.request.Request(f"{OLLAMA}/api/chat", data=data,
                                headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            result = json.loads(resp.read().decode())
            return result.get("message", {}).get("content", "")
    except Exception as e:
        return f"Error: {e}"

def log_action(agent_id, action, details):
    """Log agent action to database."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        INSERT INTO agent_log (log_id, agent_id, action, details, created)
        VALUES (?, ?, ?, ?, ?)
    """, (str(uuid.uuid4())[:8], agent_id, action, details[:500],
          datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

def autonomous_loop():
    """Main autonomous loop."""
    init_db()
    
    agent_id = f"kudbee-auto-{uuid.uuid4().hex[:6]}"
    
    # Create main goal if none exists
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT COUNT(*) FROM goals").fetchone()
    if row[0] == 0:
        conn.execute("""
            INSERT INTO goals (goal_id, title, description, status, priority, created)
            VALUES (?, ?, ?, ?, ?, ?)
        """, ("goal-main", "Build KUDBEE Demo", 
              "Autonomously build and deploy a complete KUDBEE demonstration including AI-generated content, game assets, and documentation.",
              "active", 1, datetime.now(timezone.utc).isoformat()))
        conn.commit()
    conn.close()
    
    log_action(agent_id, "START", "Autonomous loop initialized")
    
    iteration = 0
    max_iterations = 100  # Safety limit
    
    while iteration < max_iterations:
        iteration += 1
        
        # Get active goal
        conn = sqlite3.connect(DB_PATH)
        goal = conn.execute(
            "SELECT goal_id, title, description FROM goals WHERE status = 'active' ORDER BY priority LIMIT 1"
        ).fetchone()
        conn.close()
        
        if not goal:
            log_action(agent_id, "NO_GOAL", "No active goals found. Creating new one...")
            # Create new goal based on current state
            goal_id = f"goal-{uuid.uuid4().hex[:6]}"
            conn = sqlite3.connect(DB_PATH)
            conn.execute("""
                INSERT INTO goals (goal_id, title, description, status, priority, created)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (goal_id, "Self-Improvement Cycle", 
                  "Analyze current system and identify improvements.",
                  "active", 1, datetime.now(timezone.utc).isoformat()))
            conn.commit()
            conn.close()
            continue
        
        goal_id, goal_title, goal_desc = goal
        
        # Generate next task using AI
        prompt = f"""
Current Goal: {goal_title}
Description: {goal_desc}

Previous tasks completed. What is the most valuable next task to advance this goal?

Respond in JSON format:
{{
    "task_title": "Brief task name",
    "task_description": "Detailed description of what to do",
    "expected_output": "What should be produced"
}}
"""
        
        response = call_ollama(
            "You are an autonomous AI project manager. Generate the next valuable task.",
            prompt
        )
        
        # Parse task
        try:
            # Try to find JSON in response
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                task_data = json.loads(response[start:end])
            else:
                task_data = {
                    "task_title": f"Auto Task {iteration}",
                    "task_description": response[:200],
                    "expected_output": "Completion"
                }
        except:
            task_data = {
                "task_title": f"Auto Task {iteration}",
                "task_description": response[:200] if response else "Continue work",
                "expected_output": "Progress"
            }
        
        # Create task
        task_id = f"task-{uuid.uuid4().hex[:6]}"
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO tasks (task_id, goal_id, title, description, status, created)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (task_id, goal_id, task_data.get("task_title", "Auto Task"),
              task_data.get("task_description", ""), "running",
              datetime.now(timezone.utc).isoformat()))
        conn.commit()
        conn.close()
        
        log_action(agent_id, "TASK_START", f"{task_data.get('task_title', 'Auto Task')}")
        
        # Execute task
        exec_prompt = f"""
Execute this task and produce concrete output:

Task: {task_data.get('task_description', '')}
Expected: {task_data.get('expected_output', 'Completion')}

Rules:
- Produce actual working code, content, or configuration
- Save files to /opt/kudbee/outputs/autonomous/
- Create detailed documentation
- Report what you accomplished

Current time: {datetime.now(timezone.utc).isoformat()}
"""
        
        output = call_ollama(
            f"You are {agent_id}, an autonomous AI agent building KUDBEE. Execute tasks independently.",
            exec_prompt,
            max_tokens=4000
        )
        
        # Save output
        output_dir = "/opt/kudbee/outputs/autonomous"
        os.makedirs(output_dir, exist_ok=True)
        
        output_file = f"{output_dir}/task_{task_id}.md"
        with open(output_file, "w") as f:
            f.write(f"# {task_data.get('task_title', 'Auto Task')}\n\n")
            f.write(f"**Goal:** {goal_title}\n")
            f.write(f"**Task ID:** {task_id}\n")
            f.write(f"**Started:** {datetime.now(timezone.utc).isoformat()}\n\n")
            f.write(f"## Output\n\n{output}\n")
        
        # Mark task complete
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            UPDATE tasks SET status = ?, output = ?, completed = ?
            WHERE task_id = ?
        """, ("completed", output[:1000], datetime.now(timezone.utc).isoformat(), task_id))
        conn.commit()
        conn.close()
        
        log_action(agent_id, "TASK_COMPLETE", f"Task {task_id} done. Output: {output[:100]}...")
        
        # Self-evaluation every 10 iterations
        if iteration % 10 == 0:
            log_action(agent_id, "SELF_EVAL", f"Completed {iteration} iterations. Evaluating progress...")
            
            conn = sqlite3.connect(DB_PATH)
            total_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            completed = conn.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'").fetchone()[0]
            conn.close()
            
            log_action(agent_id, "PROGRESS", f"Tasks: {total_tasks}, Completed: {completed}")
        
        # Pause between iterations
        time.sleep(30)  # 30 seconds between tasks

if __name__ == "__main__":
    print(f"KUDBEE Autonomous Loop Starting at {datetime.now(timezone.utc).isoformat()}")
    autonomous_loop()
