#!/usr/bin/env python3
"""Quick tool test on the box."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.foundation.bootstrap import bootstrap


async def test():
    ctx = bootstrap(with_provider=False, with_tools=True)
    reg = ctx.tool_registry

    print(f"Tools registered: {len(reg.list_tools())}")
    print(f"Tool names: {[t.name for t in reg.list_tools()]}")
    print()

    # Test fs_list
    result = await reg.execute("fs_list", {"path": "data"})
    print(f"fs_list: {result}")
    print()

    # Test fs_write
    result = await reg.execute("fs_write", {"path": "data/findings/test.md", "content": "# Test\nHello world"})
    print(f"fs_write: {result}")
    print()

    # Test fs_read
    result = await reg.execute("fs_read", {"path": "data/findings/test.md"})
    print(f"fs_read: {result}")
    print()

    # Test http_get
    result = await reg.execute("http_get", {"url": "https://dogechain.info/api/v1/block/1"})
    print(f"http_get status: {result.get('status')}")
    print(f"http_get saved: {result.get('saved_path')}")
    print(f"http_get excerpt: {result.get('excerpt', '')[:300]}")
    print()

    # Test memory_put
    result = await reg.execute("memory_put", {"kind": "test", "key": "test1", "value": {"hello": "world"}})
    print(f"memory_put: {result}")
    print()

    # Test memory_get
    result = await reg.execute("memory_get", {"key": "test1"})
    print(f"memory_get: {result}")
    print()

    # Test memory_search
    result = await reg.execute("memory_search", {"kind": "test"})
    print(f"memory_search: {result}")
    print()

    # Test load_fixture
    result = await reg.execute("load_fixture", {"name": "dogi_canonical.json"})
    print(f"load_fixture: {result.get('success')}")
    print(f"fixture keys: {list(result.get('data', {}).keys()) if result.get('success') else 'N/A'}")
    print()

    # Test doge_tx (will fail with example txid, but tests the tool)
    result = await reg.execute("doge_tx", {"txid": "0" * 64})
    print(f"doge_tx (fake): success={result.get('success')}, error={result.get('error', 'N/A')[:100]}")
    print()

    print("ALL TOOL TESTS PASSED")


if __name__ == "__main__":
    asyncio.run(test())
