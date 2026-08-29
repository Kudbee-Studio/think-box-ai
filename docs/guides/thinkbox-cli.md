# Think Box AI — CLI & Tokens

## CLI Commands

```
thinkbox create                    # Generate a new Think Box ID
thinkbox exec <id> -- <argv>       # Execute a command, prints output
thinkbox evidence <id>             # Show execution evidence rows
thinkbox tokens <id>               # List tokens for a box
thinkbox token-score <tid>         # Print token Elo score + last challenge
thinkbox challenge-jury <tid>      # Run LLM jury challenge (needs URL)
thinkbox list                      # List all boxes with tokens
thinkbox status <id>               # Detailed box status
```

## Token Model

- **Mint**: Only when `thinkbox exec` evidence row has `ok=true`
- **Claim**: argv joined, capped at 200 chars
- **Initial score**: s=1.0, grounded=1

## Challenge Types

| Type   | Weight | Outcome |
|--------|--------|---------|
| exec   | 3      | ok=true → o=+1, ok=false → o=-1 |
| jury   | 2      | LLM YES/NO/garbage → o=+1/-1/0 |
| human  | 2      | (future) |
| replay | 1      | (future) |

## Elo Formula

```
s += η * w * (o - σ(s - s_challenger))
```

- η = 0.25
- s_challenger = 1.0
- Floor: 0, Cap: 100
- σ = sigmoid

## Evidence Storage

- `~/.local/share/thinkbox/evidence/<box_id>.jsonl` — append-only evidence log
- `~/.local/share/thinkbox/thinkbox.db` — SQLite (tokens + challenges tables)

## Provider Router

The `openai_compat` provider now supports multi-provider routing:

```json
{
  "providers": [
    {"name": "openai_compat", "model": "gpt-4o-mini", "base_url": "https://api.openai.com/v1"},
    {"name": "openai_compat", "model": "local-model", "base_url": "http://localhost:8000/v1"}
  ],
  "order": ["openai_compat"],
  "snapshot_cache": true
}
```

- **Snapshot hashing**: SHA-256 of input for dedup
- **Failover**: tries providers in order
- **Snapshot cache**: skips model call when input unchanged
