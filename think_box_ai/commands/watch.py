"""File watch command."""

from __future__ import annotations

import hashlib
import time
from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, yellow


def handle_watch(args) -> None:
    watch_path = Path(args.path)
    pattern = args.pattern

    if not watch_path.exists():
        print(yellow(f"  Path not found: {watch_path}"))
        return

    print(bold(f"\n  Watching {watch_path} for changes (pattern: {pattern})..."))
    print(dim("  Press Ctrl+C to stop.\n"))

    file_hashes: dict[str, str] = {}

    def get_file_hash(path: Path) -> str:
        try:
            return hashlib.md5(path.read_bytes()).hexdigest()
        except OSError:
            return ""

    def scan_files() -> dict[str, str]:
        files = {}
        for f in watch_path.rglob(pattern):
            if f.is_file():
                files[str(f)] = get_file_hash(f)
        return files

    file_hashes = scan_files()
    print(f"  Tracking {len(file_hashes)} files.")

    try:
        while True:
            time.sleep(2)
            current_files = scan_files()

            new = set(current_files) - set(file_hashes)
            deleted = set(file_hashes) - set(current_files)
            modified = {
                f for f in current_files
                if f in file_hashes and current_files[f] != file_hashes[f]
            }

            for f in new:
                print(f"  {green('+')} {f}")
            for f in deleted:
                print(f"  {yellow('-')} {f}")
            for f in modified:
                print(f"  {cyan('~')} {f}")

            file_hashes = current_files

    except KeyboardInterrupt:
        print(dim("\n  Watch stopped."))
