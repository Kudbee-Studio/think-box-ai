"""Plugin and skill management commands."""

from __future__ import annotations

import json
from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, yellow
from ..ui.table import render_table
from ..utils.output import is_json_mode, output_json


SKILLS_DIR = Path("skills")


def handle_skill_command(args) -> None:
    sub = args.skill_command

    if sub == "list":
        if not SKILLS_DIR.exists():
            print(dim("  No skills directory."))
            return
        skills = []
        for d in sorted(SKILLS_DIR.iterdir()):
            if d.is_dir():
                manifest = d / "skill.json"
                if manifest.exists():
                    try:
                        data = json.loads(manifest.read_text())
                        skills.append({
                            "name": data.get("name", d.name),
                            "version": data.get("version", "?"),
                            "description": data.get("description", "")[:50],
                        })
                    except (json.JSONDecodeError, OSError):
                        continue
                else:
                    skills.append({"name": d.name, "version": "?", "description": ""})
        if is_json_mode():
            output_json(skills)
            return
        if not skills:
            print(dim("  No skills installed."))
            return
        headers = ["Name", "Version", "Description"]
        rows = [[s["name"], s["version"], s["description"]] for s in skills]
        print(bold(f"\n  Installed Skills ({len(skills)}):"))
        print(render_table(headers, rows))

    elif sub == "info":
        manifest = SKILLS_DIR / args.name / "skill.json"
        if not manifest.exists():
            print(yellow(f"  Skill not found: {args.name}"))
            return
        data = json.loads(manifest.read_text())
        if is_json_mode():
            output_json(data)
            return
        print(bold(f"\n  Skill: {data.get('name', args.name)}"))
        print(dim("  " + "─" * 40))
        for key, value in data.items():
            print(f"    {bold(key):15} {value}")

    elif sub == "install":
        print(yellow("  Skill installation from registry not yet implemented."))
        print(dim("  Copy skill folder to skills/ directory manually."))
    else:
        print("Usage: thinkbox skill {list|info|install}")
