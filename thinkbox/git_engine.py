"""Git State Diff Auto-Committer for ThinkBox AI.

Automatically converts successful speculative execution receipts into clean,
atomic Git commits. Groups micro-agent task fixes into modular git branches
and generates cryptographically signed commit messages.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class CommitReceipt:
    commit_hash: str
    branch: str
    message: str
    task_id: str
    execution_time_ms: float
    tokens_used: int
    signature: str
    timestamp: str
    files_changed: list[str]


@dataclass
class GitConfig:
    signing_key: str = ""
    author_name: str = "ThinkBox AI"
    author_email: str = "agent@thinkbox.ai"
    max_files_per_commit: int = 10
    branch_prefix: str = "thinkbox/"


class GitEngine:
    def __init__(self, repo_path: str | Path = ".", config: GitConfig | None = None):
        self.repo_path = Path(repo_path).resolve()
        self.config = config or GitConfig()
        self._hmac_key = os.environ.get("THINKBOX_GIT_SIGNING_KEY", "default-signing-key-change-in-prod")

    def _run_git(self, args: list[str], check: bool = False) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git"] + args,
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            timeout=30,
            check=check,
        )

    def _sign_message(self, message: str) -> str:
        return hmac.new(
            self._hmac_key.encode(),
            message.encode(),
            hashlib.sha256,
        ).hexdigest()[:16]

    def get_current_branch(self) -> str:
        result = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"])
        return result.stdout.strip() or "main"

    def has_changes(self) -> bool:
        result = self._run_git(["status", "--porcelain"])
        return bool(result.stdout.strip())

    def get_changed_files(self) -> list[str]:
        result = self._run_git(["diff", "--name-only", "HEAD"])
        return [f for f in result.stdout.strip().split("\n") if f]

    def create_branch(self, task_id: str) -> str:
        branch_name = f"{self.config.branch_prefix}{task_id[:12]}-{int(time.time())}"
        self._run_git(["checkout", "-b", branch_name])
        return branch_name

    def stage_files(self, files: list[str]) -> None:
        for i in range(0, len(files), self.config.max_files_per_commit):
            batch = files[i:i + self.config.max_files_per_commit]
            self._run_git(["add"] + batch)

    def generate_commit_message(
        self,
        task_id: str,
        execution_time_ms: float,
        tokens_used: int,
        exit_code: int,
        summary: str = "",
    ) -> str:
        timestamp = datetime.now(timezone.utc).isoformat()
        message = (
            f"feat(thinkbox): task {task_id[:12]} complete\n\n"
            f"Execution time: {execution_time_ms:.1f}ms\n"
            f"Tokens used: {tokens_used}\n"
            f"Exit code: {exit_code}\n"
            f"Timestamp: {timestamp}\n"
        )
        if summary:
            message += f"\nSummary: {summary}"

        signature = self._sign_message(message)
        message += f"\n\nSigned: {signature}"

        return message

    def commit_receipt(
        self,
        task_id: str,
        execution_time_ms: float,
        tokens_used: int,
        exit_code: int = 0,
        summary: str = "",
        files: list[str] | None = None,
    ) -> CommitReceipt | None:
        if not self.has_changes():
            return None

        branch = self.get_current_branch()
        changed_files = files or self.get_changed_files()

        if not changed_files:
            return None

        self.stage_files(changed_files)

        message = self.generate_commit_message(
            task_id=task_id,
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used,
            exit_code=exit_code,
            summary=summary,
        )

        env = os.environ.copy()
        env["GIT_AUTHOR_NAME"] = self.config.author_name
        env["GIT_AUTHOR_EMAIL"] = self.config.author_email
        env["GIT_COMMITTER_NAME"] = self.config.author_name
        env["GIT_COMMITTER_EMAIL"] = self.config.author_email

        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(self.repo_path),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

        if result.returncode != 0:
            return None

        hash_result = self._run_git(["rev-parse", "HEAD"])
        commit_hash = hash_result.stdout.strip()

        signature = self._sign_message(message)

        return CommitReceipt(
            commit_hash=commit_hash,
            branch=branch,
            message=message,
            task_id=task_id,
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used,
            signature=signature,
            timestamp=datetime.now(timezone.utc).isoformat(),
            files_changed=changed_files,
        )

    def commit_speculative_result(
        self,
        task_id: str,
        execution_time_ms: float,
        tokens_used: int,
        exit_code: int,
        output: str = "",
    ) -> CommitReceipt | None:
        if exit_code != 0:
            return None

        summary = output[:200] if output else "Speculative execution succeeded"
        return self.commit_receipt(
            task_id=task_id,
            execution_time_ms=execution_time_ms,
            tokens_used=tokens_used,
            exit_code=exit_code,
            summary=summary,
        )

    def push_branch(self, branch: str, remote: str = "origin") -> bool:
        result = self._run_git(["push", remote, branch])
        return result.returncode == 0

    def get_commit_history(self, branch: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        cmd = ["log", f"--max-count={limit}", "--pretty=format:%H|%an|%ae|%aI|%s"]
        if branch:
            cmd.append(branch)

        result = self._run_git(cmd)
        commits = []
        for line in result.stdout.strip().split("\n"):
            if "|" in line:
                parts = line.split("|", 4)
                if len(parts) >= 5:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "email": parts[2],
                        "date": parts[3],
                        "message": parts[4],
                    })
        return commits
