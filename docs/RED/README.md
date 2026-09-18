# RED: RED File System Index

## What is RED?

RED is a structured orientation format for agents entering the project.
Each RED file covers one domain and is organized into three sections:

- **RESOURCES** — What exists (modules, classes, APIs, data stores)
- **EVENTS** — What happened (PRs, milestones, completed work)
- **DECISIONS** — What decisions were made and why (ADR-style)

## RED Files

| File | Domain | Description |
|------|--------|-------------|
| [scheduler.md](scheduler.md) | Scheduler module | 92 classes across PR #76–84 |
| [architecture.md](architecture.md) | Core architecture | Engines, layers, DAG, concurrency |
| [agents.md](agents.md) | Agent coordination | Session handoffs, workflows, docs |

## How to Use

1. New agent: Read `agents.md` first (session orientation).
2. Working on scheduling: Read `scheduler.md`.
3. Architectural question: Read `architecture.md`.
4. Cross-reference: See [index.md](index.md) for all files and quick descriptions.

## Format Legend

| Column | Meaning |
|--------|---------|
| Name | Class/function/module name |
| Type | Class, function, enum, dataclass, module, etc. |
| Location | File path and line number |
| Description | One-sentence purpose |