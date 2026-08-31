#!/usr/bin/env python3
"""Verify tool registry on box."""
import sys
sys.path.insert(0, "/workspace/home/think-box-ai")
from core.foundation.bootstrap import bootstrap

ctx = bootstrap(with_provider=False, with_tools=True)
tools = ctx.tool_registry.list_tools()
print(f"Tools registered: {len(tools)}")
for t in tools:
    print(f"  - {t.name}")
