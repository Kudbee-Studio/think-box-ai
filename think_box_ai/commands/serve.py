"""Serve command for Think Box CLI."""

from __future__ import annotations

import os
import sys


def serve(host: str = "0.0.0.0", port: int = 8000, reload: bool = False) -> None:
    """Start the FastAPI backend."""
    try:
        import uvicorn
    except ImportError:
        print("uvicorn not installed. Run: pip install uvicorn")
        sys.exit(1)

    os.environ.setdefault("THINKBOX_DEFAULT_PROVIDER", "ollama")
    uvicorn.run(
        "backend.main:app",
        host=host,
        port=port,
        reload=reload,
    )
