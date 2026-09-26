#!/usr/bin/env python3
"""Box pool management CLI.

Manage Upstash Box pool endpoints, health checks, and allocations.

Usage:
    python3 scripts/box_pool.py status                  # Show pool status
    python3 scripts/box_pool.py health                  # Check health of all boxes
    python3 scripts/box_pool.py add <url>               # Add box to pool
    python3 scripts/box_pool.py remove <url>            # Remove box from pool
    python3 scripts/box_pool.py allocate <agent_id>     # Allocate agent to box
    python3 scripts/box_pool.py release <agent_id>      # Release agent
    python3 scripts/box_pool.py assignments             # Show all assignments
    python3 scripts/box_pool.py clear-assignments       # Clear all assignments
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from thinkbox.substrate import BoxPool, BoxPoolError
from thinkbox.box_assignment_store import BoxAssignmentStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Main CLI handler."""
    parser = argparse.ArgumentParser(description="Box pool management CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Status command
    subparsers.add_parser("status", help="Show pool status")
    
    # Health command
    subparsers.add_parser("health", help="Check health of all boxes")
    
    # Add box
    add_parser = subparsers.add_parser("add", help="Add box to pool")
    add_parser.add_argument("url", help="Box endpoint URL")
    
    # Remove box
    remove_parser = subparsers.add_parser("remove", help="Remove box from pool")
    remove_parser.add_argument("url", help="Box endpoint URL")
    
    # Allocate
    allocate_parser = subparsers.add_parser("allocate", help="Allocate agent to box")
    allocate_parser.add_argument("agent_id", help="Agent ID")
    
    # Release
    release_parser = subparsers.add_parser("release", help="Release agent")
    release_parser.add_argument("agent_id", help="Agent ID")
    
    # Assignments
    subparsers.add_parser("assignments", help="Show all assignments")
    
    # Clear assignments
    subparsers.add_parser("clear-assignments", help="Clear all assignments")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    try:
        pool = BoxPool()
        store = BoxAssignmentStore()
        
        if args.command == "status":
            status = pool.get_status()
            print(json.dumps(status, indent=2))
            return 0
        
        elif args.command == "health":
            health = pool.check_health()
            print(json.dumps(health, indent=2))
            return 0
        
        elif args.command == "add":
            pool._health_checker.register(args.url)
            logger.info(f"Added box endpoint: {args.url}")
            status = pool.get_status()
            print(json.dumps(status, indent=2))
            return 0
        
        elif args.command == "remove":
            # Simple removal from health checker
            with pool._lock:
                endpoints = pool._health_checker._endpoints
                if args.url in endpoints:
                    del endpoints[args.url]
                    logger.info(f"Removed box endpoint: {args.url}")
            status = pool.get_status()
            print(json.dumps(status, indent=2))
            return 0
        
        elif args.command == "allocate":
            try:
                box_url = pool.allocate(args.agent_id)
                store.set_assignment(args.agent_id, box_url)
                result = {
                    "agent_id": args.agent_id,
                    "box_url": box_url,
                    "status": "allocated",
                }
                print(json.dumps(result, indent=2))
                return 0
            except BoxPoolError as e:
                logger.error(f"Allocation failed: {e}")
                return 1
        
        elif args.command == "release":
            pool.release(args.agent_id)
            store.remove_assignment(args.agent_id)
            logger.info(f"Released agent: {args.agent_id}")
            return 0
        
        elif args.command == "assignments":
            status = store.get_status()
            print(json.dumps(status, indent=2))
            return 0
        
        elif args.command == "clear-assignments":
            store.clear_all()
            logger.info("Cleared all assignments")
            return 0
    
    except Exception as e:
        logger.error(f"Command failed: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
