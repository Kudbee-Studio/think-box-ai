#!/usr/bin/env python3
"""kudbEE CLI — Remote Connection & Auto-Discovery.

Issue #16 — Phase 4: kudbEE CLI Remote Connection
"""

import json
import socket
import subprocess
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path.home() / ".config" / "kudbee" / "remote.json"


class RemoteConnection:
    """Manage remote connections to kudbEE agents."""

    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text())
        return {"hosts": [], "default": None}

    def _save_config(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(self.config, indent=2))

    def add_host(self, name: str, host: str, port: int = 22, user: str = "root"):
        """Add a remote host."""
        entry = {"name": name, "host": host, "port": port, "user": user}
        self.config["hosts"].append(entry)
        if not self.config["default"]:
            self.config["default"] = name
        self._save_config()
        print(f"Added host: {name} ({user}@{host}:{port})")

    def remove_host(self, name: str):
        """Remove a remote host."""
        self.config["hosts"] = [h for h in self.config["hosts"] if h["name"] != name]
        if self.config["default"] == name:
            self.config["default"] = self.config["hosts"][0]["name"] if self.config["hosts"] else None
        self._save_config()
        print(f"Removed host: {name}")

    def list_hosts(self):
        """List all configured hosts."""
        for h in self.config["hosts"]:
            default = " (default)" if h["name"] == self.config["default"] else ""
            print(f"  {h['name']}: {h['user']}@{h['host']}:{h['port']}{default}")

    def connect(self, name: Optional[str] = None):
        """SSH to a remote host."""
        target = name or self.config["default"]
        if not target:
            print("No host specified. Use: kudbee remote add <name> <host>")
            return

        host = next((h for h in self.config["hosts"] if h["name"] == target), None)
        if not host:
            print(f"Host not found: {target}")
            return

        cmd = f"ssh -p {host['port']} {host['user']}@{host['host']}"
        print(f"Connecting: {cmd}")
        subprocess.run(cmd, shell=True)

    def discover(self, subnet: str = "10.0.0"):
        """Auto-discover kudbEE agents on the local network."""
        print(f"Scanning {subnet}.0/24 for kudbEE agents...")
        found = []
        for i in range(1, 255):
            ip = f"{subnet}.{i}"
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.1)
                result = sock.connect_ex((ip, 22))
                if result == 0:
                    print(f"  Found: {ip}")
                    found.append(ip)
                sock.close()
            except Exception:
                pass
        print(f"Scan complete. {len(found)} hosts found.")
        return found


def main():
    import sys
    conn = RemoteConnection()

    if len(sys.argv) < 2:
        print("Usage: kudbee remote <add|remove|list|connect|discover>")
        return

    cmd = sys.argv[1]
    if cmd == "add" and len(sys.argv) >= 4:
        conn.add_host(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 22)
    elif cmd == "remove" and len(sys.argv) >= 3:
        conn.remove_host(sys.argv[2])
    elif cmd == "list":
        conn.list_hosts()
    elif cmd == "connect":
        conn.connect(sys.argv[2] if len(sys.argv) > 2 else None)
    elif cmd == "discover":
        conn.discover(sys.argv[2] if len(sys.argv) > 2 else "10.0.0")
    else:
        print(f"Unknown command: {cmd}")


if __name__ == "__main__":
    main()
