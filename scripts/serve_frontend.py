#!/usr/bin/env python3
"""Simple static file server for Think Box AI frontend."""

import os
import sys
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler


def main():
    public_dir = Path(__file__).resolve().parent.parent / "public"
    os.chdir(str(public_dir))

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    server = HTTPServer(("0.0.0.0", port), SimpleHTTPRequestHandler)

    print(f"Think Box AI frontend running at:")
    print(f"  http://localhost:{port}/")
    print(f"  http://localhost:{port}/jobs/")
    print(f"  http://localhost:{port}/findings/")
    print(f"  http://localhost:{port}/about/")
    print()
    print("Press Ctrl+C to stop.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
