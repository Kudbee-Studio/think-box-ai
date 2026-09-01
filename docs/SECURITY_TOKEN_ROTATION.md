# Security: GitHub Token Rotation Checklist

**Issue:** #4 — ROTATE GH TOKEN
**Severity:** CRITICAL
**Status:** Action required by Kudbee

## Immediate Actions (Kudbee must do)

1. **Go to** GitHub → Settings → Developer settings → Personal access tokens
2. **Delete** the exposed token (see issue #4 for the token value)
3. **Generate** a new token with minimal permissions (repo read-only)
4. **Update** the Upstash Box MCP server config with new token
5. **Verify** no other repos or services use the same token

## Verification Steps

After rotating, verify no secrets remain:

```bash
# Check for any leaked secrets in git history
git log --all -p | grep -i "token\|secret\|key" && echo "REVIEW NEEDED" || echo "CLEAN"

# Scan working tree
grep -r "ghp_\|sk-\|gsk_" --include="*.md" --include="*.json" --include="*.py" . 2>/dev/null
```

## Prevention

- Never commit tokens to git
- Use environment variables or secret managers
- Rotate tokens every 90 days
- Use fine-grained tokens with minimal scope
