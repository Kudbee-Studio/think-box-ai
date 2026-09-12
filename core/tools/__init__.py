"""Built-in tools for THINK BOX AI."""

from __future__ import annotations

from core.tools.fs import fs_read, fs_write, fs_list
from core.tools.http import http_get
from core.tools.memory import memory_put, memory_get, memory_search
from core.tools.memory_query import memory_query
from core.tools.shell_exec import shell_exec_async as shell_exec

# Alias exports for architecture compatibility (file_read/file_write/http_request)
file_read = fs_read
file_write = fs_write
http_request = http_get

__all__ = [
    "fs_read",
    "fs_write",
    "fs_list",
    "http_get",
    "memory_put",
    "memory_get",
    "memory_search",
    "memory_query",
    "shell_exec",
    "file_read",
    "file_write",
    "http_request",
]
