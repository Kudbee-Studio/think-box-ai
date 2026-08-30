#!/usr/bin/env python3
"""KUDBEE Adversarial Red-Team Loop

Pairs Think Boxes against each other:
- Box A generates hypotheses/specs
- Box B acts as hostile verifier
- Winner gains confidence, loser loses tokens
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = "/opt/kudbee/memory/think_tokens.db"


class RedTeamLoop:
    """Adversarial testing between Think Boxes."""
    
    def __init__(self, ollama_url: str = "http://localhost:11434"):
        self.ollama_url = ollama_url
        self.boxes = [
            "director-alpha", "director-beta",
            "security-hardener", "speed-optimizer",
            "token-economist", "quality-critic",
        ]
    
    def _call_ollama(self, model: str, prompt: str, max_tokens: int = 500) -> str:
        """Call Ollama API."""
        import urllib.request
        
        data = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"max_tokens": max_tokens}
        }).encode()
        
        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode())
                return result.get("response", "")
        except Exception as e:
            return f"Error: {e}"
    
    def run_challenge(self, domain: str = "security") -> dict:
        """Run a single red-team challenge."""
        attacker = "security-hardener"
        defender = "director-alpha"
        
        # Step 1: Defender generates a spec
        defender_prompt = f"""You are a {defender}. Generate a brief system specification for {domain}. 
Include: architecture, key components, and security measures. Keep it under 200 words."""
        
        defender_spec = self._call_ollama("gpt-oss:20b", defender_prompt)
        
        # Step 2: Attacker tries to break it
        attacker_prompt = f"""You are a hostile red-teamer. Analyze this system spec and find 3 critical vulnerabilities:

{defender_spec}

For each vulnerability, provide:
- Vulnerability name
- Severity (critical/high/medium)
- Exploitation method
- Recommended fix"""
        
        attacker_analysis = self._call_ollama("gpt-oss:120b", attacker_prompt)
        
        # Step 3: Score the challenge
        # If attacker found real issues, they win
        success = "vulnerability" in attacker_analysis.lower() or "critical" in attacker_analysis.lower()
        
        result = {
            "challenge_id": f"CHAL-{uuid.uuid4().hex[:8]}",
            "domain": domain,
            "attacker": attacker,
            "defender": defender,
            "defender_spec": defender_spec[:500],
            "attacker_analysis": attacker_analysis[:500],
            "winner": attacker if success else defender,
            "confidence_change": 0.1 if success else -0.05,
            "created": datetime.now(timezone.utc).isoformat(),
        }
        
        # Store in database
        conn = sqlite3.connect(DB_PATH)
        conn.execute("""
            INSERT INTO red_team_challenges 
            (challenge_id, attacker_box, defender_box, token_id, challenge_type, payload, result, winner, created, resolved)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result["challenge_id"], attacker, defender, 
            f"THINK-{uuid.uuid4().hex[:8]}", domain,
            defender_spec[:200], attacker_analysis[:200],
            result["winner"], result["created"], result["created"]
        ))
        conn.commit()
        conn.close()
        
        return result
    
    def run_swarm_consensus(self, token_id: str, proposal: str) -> dict:
        """Run swarm consensus vote on a proposal."""
        votes = []
        
        voting_boxes = [
            ("security-hardener", 0.9),
            ("speed-optimizer", 0.8),
            ("token-economist", 0.85),
            ("quality-critic", 0.75),
        ]
        
        for box_id, expertise in voting_boxes:
            prompt = f"""You are {box_id} with expertise weight {expertise}. 
Evaluate this proposal and vote approve/reject with reasoning:

{proposal}

Respond in JSON: {{"vote": "approve|reject", "confidence": 0-1, "reasoning": "..."}}"""
            
            response = self._call_ollama("gpt-oss:20b", prompt, max_tokens=200)
            
            # Parse vote (simplified)
            vote = "approve" if "approve" in response.lower() else "reject"
            confidence = expertise  # Use expertise as base confidence
            
            votes.append({
                "box": box_id,
                "vote": vote,
                "confidence": confidence,
                "reasoning": response[:100],
            })
            
            # Record vote
            conn = sqlite3.connect(DB_PATH)
            conn.execute("""
                INSERT INTO swarm_votes (vote_id, token_id, box_id, vote, confidence, reasoning, created)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                f"VOTE-{uuid.uuid4().hex[:8]}", token_id, box_id,
                vote, confidence, response[:100],
                datetime.now(timezone.utc).isoformat()
            ))
            conn.commit()
            conn.close()
        
        # Calculate consensus
        approve_weight = sum(v["confidence"] for v in votes if v["vote"] == "approve")
        total_weight = sum(v["confidence"] for v in votes)
        approval_rate = approve_weight / total_weight if total_weight > 0 else 0
        
        return {
            "token_id": token_id,
            "proposal": proposal[:100],
            "votes": votes,
            "approval_rate": round(approval_rate, 2),
            "consensus": approval_rate >= 0.6,
        }


if __name__ == "__main__":
    loop = RedTeamLoop()
    print("Red-Team Loop initialized!")
    print(f"Boxes: {loop.boxes}")
    
    # Run a test challenge
    print("\nRunning security challenge...")
    result = loop.run_challenge("security")
    print(f"Winner: {result['winner']}")
    print(f"Confidence change: {result['confidence_change']}")
