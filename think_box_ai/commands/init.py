"""Project initialization command."""

from __future__ import annotations

import json
from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, yellow
from ..ui.prompt import confirm, input_text, print_step, print_success, print_warning


def handle_init(args) -> None:
    print(bold("\n  Think Box AI — Project Initialization"))
    print(dim("  " + "─" * 50))

    _init_directories()
    _init_config()
    _init_gitignore()
    _init_env_example()
    _init_templates()
    _init_readme()

    print(bold("\n  Initialization complete!"))
    print(f"  Run {cyan('thinkbox doctor')} to verify your setup.")
    print(f"  Run {cyan('thinkbox serve')} to start the backend.")


def _init_directories() -> None:
    print_step(1, 6, "Creating directories")
    dirs = [
        "data",
        "data/jobs",
        "data/findings",
        "data/raw",
        "data/fixtures",
        "data/templates",
        ".thinkbox",
    ]
    for d in dirs:
        path = Path(d)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            print(f"    {green('Created')} {d}/")
        else:
            print(f"    {dim('Exists')} {d}/")


def _init_config() -> None:
    print_step(2, 6, "Creating config")
    config_file = Path(".thinkbox/config.json")
    if config_file.exists():
        print(f"    {dim('Config exists, skipping')}")
        return

    config = {
        "default_provider": "openai_compat",
        "default_model": "gpt-4o-mini",
        "max_think_box_depth": 2,
        "audit_log_retention_days": 90,
    }
    config_file.write_text(json.dumps(config, indent=2))
    print_success("Created .thinkbox/config.json")


def _init_gitignore() -> None:
    print_step(3, 6, "Updating .gitignore")
    gitignore = Path(".gitignore")
    entries = [".thinkbox/", ".env", "*.db", "__pycache__/"]
    existing = gitignore.read_text() if gitignore.exists() else ""

    new_entries = [e for e in entries if e not in existing]
    if new_entries:
        with open(gitignore, "a") as f:
            if existing and not existing.endswith("\n"):
                f.write("\n")
            f.write("\n".join(new_entries) + "\n")
        print_success(f"Added {len(new_entries)} entries to .gitignore")
    else:
        print(dim("    Already up to date"))


def _init_env_example() -> None:
    print_step(4, 6, "Creating .env.example")
    env_file = Path(".env.example")
    if env_file.exists():
        print(dim("    Already exists"))
        return

    env_file.write_text(
        "# Think Box AI Environment Configuration\n"
        "THINKBOX_DEFAULT_PROVIDER=openai_compat\n"
        "THINKBOX_DEFAULT_MODEL=gpt-4o-mini\n"
        "THINKBOX_OPENAI_COMPAT_API_KEY=\n"
        "THINKBOX_OPENAI_COMPAT_BASE_URL=https://api.openai.com/v1\n"
    )
    print_success("Created .env.example")


def _init_templates() -> None:
    print_step(5, 6, "Creating job templates")
    templates_dir = Path("data/templates")
    templates = {
        "research": {
            "intent": "Research a topic and produce findings",
            "hat": "researcher",
        },
        "verify": {
            "intent": "Verify a claim using multiple sources",
            "hat": "researcher",
        },
        "execute": {
            "intent": "Execute a task with tools",
            "hat": "runner",
        },
    }

    for name, data in templates.items():
        path = templates_dir / f"{name}.json"
        if not path.exists():
            path.write_text(json.dumps(data, indent=2))
            print(f"    {green('Created')} {name}.json")
        else:
            print(f"    {dim('Exists')} {name}.json")


def _init_readme() -> None:
    print_step(6, 6, "Project README")
    readme = Path("README.md")
    if readme.exists():
        print(dim("    Already exists"))
        return

    readme.write_text(
        "# Think Box AI\n\n"
        "Agent execution environment for research and verification.\n\n"
        "## Quick Start\n\n"
        "```bash\n"
        "thinkbox init      # Initialize project\n"
        "thinkbox doctor    # Check system health\n"
        "thinkbox serve     # Start backend\n"
        "```\n\n"
        "## Commands\n\n"
        "- `thinkbox job` — Job management\n"
        "- `thinkbox memory` — Project memory\n"
        "- `thinkbox config` — Configuration\n"
        "- `thinkbox findings` — Browse findings\n"
        "- `thinkbox search` — Full-text search\n"
        "- `thinkbox doctor` — System diagnostics\n"
    )
    print_success("Created README.md")
