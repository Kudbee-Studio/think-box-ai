"""Full-text search command."""

from __future__ import annotations

from pathlib import Path

from ..ui.colors import bold, cyan, dim, green, yellow
from ..utils.output import is_json_mode, output_json

from core.indexing.database import init_db
from core.indexing.search import SearchEngine


def handle_search(args) -> None:
    init_db()
    engine = SearchEngine()
    query = args.query
    limit = args.limit

    results = {"query": query, "results": []}

    if args.type in ("memory", "all"):
        mem_results = engine.search_memory(query, limit=limit)
        for r in mem_results:
            results["results"].append({
                "type": "memory",
                "key": r.key,
                "value": r.value[:200],
                "source": r.source,
            })

    if args.type in ("jobs", "all"):
        from pathlib import Path
        import json
        jobs_dir = Path("data/jobs")
        if jobs_dir.exists():
            for f in jobs_dir.glob("*.json"):
                try:
                    job = json.loads(f.read_text())
                    if query.lower() in json.dumps(job).lower():
                        results["results"].append({
                            "type": "job",
                            "id": job.get("id", ""),
                            "intent": job.get("intent", ""),
                            "state": job.get("state", ""),
                        })
                except (json.JSONDecodeError, OSError):
                    continue

    if args.type in ("findings", "all"):
        findings_dir = Path("data/findings")
        if findings_dir.exists():
            for f in findings_dir.glob("*.md"):
                content = f.read_text()
                if query.lower() in content.lower():
                    results["results"].append({
                        "type": "finding",
                        "name": f.stem,
                        "preview": content[:200].replace("\n", " "),
                    })

    if is_json_mode():
        output_json(results)
        return

    print(bold(f'\n  Search: "{query}"'))
    print(dim("  " + "─" * 50))

    if not results["results"]:
        print(dim("  No results found."))
        return

    print(f"  Found {cyan(str(len(results['results'])))} results:\n")

    for r in results["results"]:
        rtype = r["type"]
        if rtype == "memory":
            print(f"  {green('[memory]')} {bold(r['key'])}")
            print(f"    {r['value'][:100]}")
        elif rtype == "job":
            print(f"  {cyan('[job]')} {bold(r.get('id', '')[:12])}")
            print(f"    {r.get('intent', '')[:80]}")
        elif rtype == "finding":
            print(f"  {yellow('[finding]')} {bold(r['name'])}")
            print(f"    {r['preview'][:100]}")
        print()
