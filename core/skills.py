#!/usr/bin/env python3
"""Skills and plugins system for Think Box AI CLI.

Installable skill packages that extend CLI functionality.
"""

from __future__ import annotations

import json
import importlib
from pathlib import Path
from typing import Any

SKILLS_PATH = Path("skills")


class Skill:
    """A loadable skill/plugin."""

    def __init__(self, name: str, description: str, version: str = "1.0.0"):
        self.name = name
        self.description = description
        self.version = version
        self.commands: dict[str, callable] = {}

    def register_command(self, name: str, func: callable):
        self.commands[name] = func

    def execute(self, command: str, args: list[str]) -> Any:
        if command in self.commands:
            return self.commands[command](*args)
        raise ValueError(f"Unknown command: {command}")


class SkillRegistry:
    """Manage installed skills."""

    def __init__(self):
        self.skills: dict[str, Skill] = {}
        SKILLS_PATH.mkdir(parents=True, exist_ok=True)
        self._load_builtin_skills()

    def _load_builtin_skills(self):
        """Load built-in skills."""
        # Doginals research skill
        doginals = Skill("doginals", "Doginals research toolkit")
        doginals.register_command("search", self._cmd_doginals_search)
        doginals.register_command("verify", self._cmd_doginals_verify)
        self.skills["doginals"] = doginals

        # Security skill
        security = Skill("security", "Security analysis toolkit")
        security.register_command("audit", self._cmd_security_audit)
        security.register_command("scan", self._cmd_security_scan)
        self.skills["security"] = security

        # Indexer skill
        indexer = Skill("indexer", "Indexer comparison toolkit")
        indexer.register_command("compare", self._cmd_indexer_compare)
        indexer.register_command("health", self._cmd_indexer_health)
        self.skills["indexer"] = indexer

    def _cmd_doginals_search(self, query: str):
        return f"Searching Doginals for: {query}"

    def _cmd_doginals_verify(self, inscription_id: str):
        return f"Verifying inscription: {inscription_id}"

    def _cmd_security_audit(self, address: str):
        return f"Auditing: {address}"

    def _cmd_security_scan(self, target: str):
        return f"Scanning: {target}"

    def _cmd_indexer_compare(self, inscription_id: str):
        return f"Comparing indexers for: {inscription_id}"

    def _cmd_indexer_health(self):
        return "Checking indexer health"

    def install(self, name: str, source: str | Path):
        """Install a skill from a directory or git repo."""
        source = Path(source)
        if source.is_dir():
            manifest = source / "skill.json"
            if manifest.exists():
                data = json.loads(manifest.read_text())
                skill = Skill(data["name"], data.get("description", ""), data.get("version", "1.0.0"))
                target = SKILLS_PATH / name
                if target.exists():
                    import shutil
                    shutil.rmtree(target)
                import shutil
                shutil.copytree(source, target)
                self.skills[name] = skill
                return f"Installed: {name}"
        raise ValueError(f"Invalid skill source: {source}")

    def uninstall(self, name: str):
        """Remove an installed skill."""
        if name in self.skills:
            del self.skills[name]
            target = SKILLS_PATH / name
            if target.exists():
                import shutil
                shutil.rmtree(target)
            return f"Uninstalled: {name}"
        raise ValueError(f"Skill not found: {name}")

    def list_skills(self) -> list[dict]:
        """List all installed skills."""
        return [{"name": s.name, "description": s.description, "version": s.version, "commands": list(s.commands.keys())} for s in self.skills.values()]

    def execute(self, skill_name: str, command: str, args: list[str]):
        """Execute a skill command."""
        skill = self.skills.get(skill_name)
        if not skill:
            raise ValueError(f"Skill not found: {skill_name}")
        return skill.execute(command, args)


# Global registry
skills = SkillRegistry()
