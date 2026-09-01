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

```bash
# Check if token appears in any commits
git log --all -p | grep "ghp_" && echo "FOUND" || echo "CLEAN"

# Check if token appears in any files
grep -r "ghp_" --include="*.md" --include="*.json" --include="*.py" . 2>/dev/null

# Check environment
echo "UPSTASH_BOX_API_KEY=$UPSTASH_BOX_API_KEY"
```

## Prevention

- Never commit tokens to git
- Use environment variables or secret managers
- Rotate tokens every 90 days
- Use fine-grained tokens with minimal scope
