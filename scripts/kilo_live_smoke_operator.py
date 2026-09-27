#!/usr/bin/env python3
"""KILO live-smoke operator CLI (PR #153) — hermetic artifact write + audit flip candidate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from thinkbox.kilo_live_smoke_evidence import validate_smoke_evidence_document
from thinkbox.kilo_live_smoke_operator import (
    DEFAULT_AUDIT_PRIOR_REL,
    build_hermetic_smoke_evidence,
    load_audit_prior_pass,
    load_fixture,
    load_json_file,
    write_audit_flip_candidate_file,
    write_smoke_evidence_artifact,
)


def _cmd_write(args: argparse.Namespace) -> int:
    if args.fixture:
        doc = load_fixture(args.fixture)
    elif args.stdin:
        doc = json.load(sys.stdin)
    else:
        receipt_ids = args.receipt_id or ["rcpt_operator_a", "rcpt_operator_b"]
        etags = args.etag or ["etag_operator_a", "etag_operator_b"]
        doc, build_v = build_hermetic_smoke_evidence(
            evidence_id=args.evidence_id or "kilo_live_smoke_operator_cli",
            receipt_ids=receipt_ids,
            etags=etags,
            founder_ack_marker_present=args.founder_ack_marker,
            box_url_present=args.box_url_present,
            live_api_called=args.live_api_called,
            live_verified=args.live_verified,
        )
        if build_v:
            print(
                json.dumps(
                    {"ok": False, "violations": [v.__dict__ for v in build_v]},
                    indent=2,
                )
            )
            return 1
    out_path = Path(args.output) if args.output else None
    if out_path and not out_path.is_absolute():
        out_path = REPO_ROOT / out_path
    result = write_smoke_evidence_artifact(doc, path=out_path)
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    if result.document:
        print(json.dumps({"document": result.document}, indent=2), file=sys.stderr)
    return 0 if result.ok else 1


def _cmd_validate(args: argparse.Namespace) -> int:
    if args.fixture:
        doc = load_fixture(args.fixture)
    elif args.path:
        doc = load_json_file(REPO_ROOT / args.path)
    else:
        doc = json.load(sys.stdin)
    artifact_exists = bool(args.artifact_exists)
    val = validate_smoke_evidence_document(doc, artifact_exists=artifact_exists)
    print(
        json.dumps(
            {
                "ok": val.ok,
                "violations": [
                    {"code": v.code, "message": v.message, "path": v.path}
                    for v in val.violations
                ],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if val.ok else 1


def _cmd_audit_flip(args: argparse.Namespace) -> int:
    if args.evidence_fixture:
        evidence = load_fixture(args.evidence_fixture)
    elif args.evidence_path:
        evidence = load_json_file(REPO_ROOT / args.evidence_path)
    else:
        evidence = json.load(sys.stdin)
    prior = args.audit_prior or str(DEFAULT_AUDIT_PRIOR_REL)
    out = Path(args.output) if args.output else None
    if out and not out.is_absolute():
        out = REPO_ROOT / out
    path, candidate = write_audit_flip_candidate_file(
        evidence,
        audit_prior_rel=prior,
        out_path=out,
        artifact_exists=args.artifact_exists,
    )
    print(
        json.dumps(
            {
                "ok": True,
                "candidate_path": str(path.relative_to(REPO_ROOT)),
                "audit_flip_status": candidate.get("audit_flip_status"),
                "live_verified": (candidate.get("four_state") or {}).get("live_verified"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def _cmd_summary(_args: argparse.Namespace) -> int:
    from thinkbox.kilo_live_smoke_operator import live_smoke_operator_contract_summary

    print(json.dumps(live_smoke_operator_contract_summary(), indent=2, sort_keys=True))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="KILO live-smoke operator (PR #153)")
    sub = parser.add_subparsers(dest="command", required=True)

    write_p = sub.add_parser("write", help="Validate and write kilo_live_smoke_*.json")
    write_p.add_argument("--fixture", help="Fixture name under data/kilo_live_smoke_operator/fixtures")
    write_p.add_argument("--stdin", action="store_true", help="Read evidence JSON from stdin")
    write_p.add_argument("--output", help="Output path (repo-relative or absolute)")
    write_p.add_argument("--evidence-id")
    write_p.add_argument("--receipt-id", action="append")
    write_p.add_argument("--etag", action="append")
    write_p.add_argument("--founder-ack-marker", action="store_true")
    write_p.add_argument("--box-url-present", action="store_true")
    write_p.add_argument("--live-api-called", action="store_true")
    write_p.add_argument("--live-verified", action="store_true")
    write_p.set_defaults(func=_cmd_write)

    val_p = sub.add_parser("validate", help="Validate evidence JSON")
    val_p.add_argument("--fixture")
    val_p.add_argument("--path")
    val_p.add_argument("--artifact-exists", action="store_true")
    val_p.set_defaults(func=_cmd_validate)

    flip_p = sub.add_parser("audit-flip-candidate", help="Write audit flip candidate JSON")
    flip_p.add_argument("--evidence-fixture")
    flip_p.add_argument("--evidence-path")
    flip_p.add_argument("--audit-prior", default=str(DEFAULT_AUDIT_PRIOR_REL))
    flip_p.add_argument("--output")
    flip_p.add_argument("--artifact-exists", action="store_true")
    flip_p.set_defaults(func=_cmd_audit_flip)

    sum_p = sub.add_parser("summary", help="Print operator contract summary")
    sum_p.set_defaults(func=_cmd_summary)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
