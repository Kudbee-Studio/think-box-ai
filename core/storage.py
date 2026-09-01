"""File storage for Think Box AI.

Supports: local filesystem, S3-compatible (MinIO, AWS S3).
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import BinaryIO

from core.foundation.logging import get_logger

logger = get_logger(__name__)


class LocalStorage:
    def __init__(self, base_path: str = "data/storage"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, data: bytes) -> str:
        path = self.base_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path)

    def load(self, name: str) -> bytes:
        path = self.base_path / name
        if not path.exists():
            raise FileNotFoundError(f"File not found: {name}")
        return path.read_bytes()

    def delete(self, name: str):
        path = self.base_path / name
        if path.exists():
            path.unlink()

    def exists(self, name: str) -> bool:
        return (self.base_path / name).exists()

    def list(self, prefix: str = "") -> list[str]:
        dir_path = self.base_path / prefix
        if not dir_path.exists():
            return []
        return [str(f.relative_to(self.base_path)) for f in dir_path.rglob("*") if f.is_file()]

    def hash(self, name: str) -> str:
        data = self.load(name)
        return hashlib.sha256(data).hexdigest()


class S3Storage:
    """S3-compatible storage (MinIO, AWS S3, etc.)."""

    def __init__(self, endpoint: str, bucket: str, access_key: str, secret_key: str):
        self.endpoint = endpoint.rstrip("/")
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key

    def save(self, name: str, data: bytes) -> str:
        import urllib.request, hmac, hashlib, datetime
        url = f"{self.endpoint}/{self.bucket}/{name}"
        headers = {
            "Content-Type": "application/octet-stream",
            "x-amz-date": datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
        }
        req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
        urllib.request.urlopen(req, timeout=30)
        return url

    def load(self, name: str) -> bytes:
        url = f"{self.endpoint}/{self.bucket}/{name}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()

    def delete(self, name: str):
        url = f"{self.endpoint}/{self.bucket}/{name}"
        req = urllib.request.Request(url, method="DELETE")
        urllib.request.urlopen(req, timeout=10)


def get_storage() -> LocalStorage:
    """Get storage backend based on config."""
    return LocalStorage()
