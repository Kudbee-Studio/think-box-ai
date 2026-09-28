# SECURITY CHECKLIST — kudbEE Agent OS

**Purpose:** Every agent session MUST run this checklist before committing code or accessing production systems.

**Last updated:** 2026-09-28  
**Canonical location:** `docs/SECURITY_CHECKLIST.md`

---

## Session Start Checklist (REQUIRED)

Run these checks at the beginning of every session:

### 1. Verify .env is Secure

```bash
# Check that .env exists locally and is NOT committed
git status | grep -i ".env" || echo "✅ .env not tracked by git"

# Verify .gitignore protects .env
grep "\.env" .gitignore && echo "✅ .env is gitignored"

# Check file permissions (should be 600)
ls -la .env | awk '{print $1, $NF}' | grep "600 .env" && echo "✅ .env has secure permissions (600)"
```

### 2. Test API Credentials (If Working with UpCloud/Upstash)

#### UpCloud (Preferred: Use Official CLI)

```bash
# Install UpCloud CLI (one-time)
python3 -m pip install upcloud-cli

# Configure (one-time)
upctl account show  # Will prompt for credentials, saves to ~/.upcloud/config

# Verify in future sessions (official method - RECOMMENDED)
python3 scripts/verify_upcloud_cli.py
# Exit code: 0 = valid, 1 = not installed, 2 = not authenticated

# Or test directly with CLI
upctl account show       # Show account info
upctl server list        # List all servers
```

#### UpCloud (Fallback: HTTP API)

```bash
# If upctl is not available, test via HTTP API
python3 scripts/verify_upcloud_credentials.py

# Exit code:
# 0 = credentials valid, API responsive
# 1 = credentials missing or invalid
# 2 = API unreachable
```

#### Upstash (If needed)

```bash
# Test Upstash Vector credentials
# python3 scripts/verify_upstash_vector_credentials.py  # (TBD)
```

**Recommendation:** Use `upctl` for production work. It's the official UpCloud CLI and handles authentication, certificate validation, and rate limiting automatically.

### 3. Scan for Leaked Secrets Before Committing

```bash
# Scan staged files for credentials
python3 scripts/scan_doc_secrets.py

# Check git history for recent secret leaks
git log --all -p --follow -S "UPCLOUD_API_KEY" -- .env* || echo "✅ No secret commits found"
```

### 4. Verify No Credentials in Output

Before closing a session, check:

- ❌ Terminal output pasted anywhere public (GitHub, Discord, etc)?
- ❌ Commit messages contain API keys or tokens?
- ❌ Proof artifacts contain plaintext credentials?
- ❌ Documentation files reference live token values?

**If yes to any:** DO NOT PUSH. Revoke the token immediately:
- UpCloud: `https://hub.upcloud.com/account/profile/authentication`
- Upstash: Regenerate in dashboard
- Inception: Generate new `INCEPTION_API_KEY`

---

## Credential Management

### Environment Variables (Canonical)

| Variable | Purpose | Scope | Rotation |
|----------|---------|-------|----------|
| `THINKBOX_UPCLOUD_API_TOKEN` | UpCloud API (control plane) | Read-only test; no SSH | 90 days |
| `UPSTASH_PUBLIC_BOX_URL` | Upstash Box execution endpoint | Execution substrate | On access deny |
| `UPSTASH_PUBLIC_BOX_TOKEN` | Upstash Box authentication | Execution substrate | On access deny |
| `INCEPTION_API_KEY` | Mercury-2 model inference | Hermetic only (no live in CI) | 90 days |
| `THINKBOX_API_KEYS` | Think Job access control (multi-tenant) | HTTP bearer auth | On revoke |
| `THINKBOX_API_KEY` | Local/hermetic Think Job key | Hermetic/e2e tests | Session-scoped |

### Rules

1. **Never commit `.env` files** (even `.env.example`)
   - `.env` and `.env.*` are in `.gitignore`
   - Always load from environment at runtime

2. **Never print credentials in logs**
   - Use redaction helpers: `token[:8] + "..." + token[-4:]`
   - Fail-closed on credential errors (don't reveal why)

3. **Never embed credentials in code**
   ```python
   # ❌ BAD
   UPCLOUD_TOKEN = "abc123xyz789"
   
   # ✅ GOOD
   UPCLOUD_TOKEN = os.environ.get('THINKBOX_UPCLOUD_API_TOKEN')
   if not UPCLOUD_TOKEN:
       raise RuntimeError("THINKBOX_UPCLOUD_API_TOKEN not set")
   ```

4. **Never pass credentials as function arguments**
   ```python
   # ❌ BAD
   api_client = UpCloudClient(token=token_value)
   
   # ✅ GOOD
   api_client = UpCloudClient()  # Reads env internally
   ```

5. **Never include credentials in proof artifacts**
   - Proof must have `live_verified: true` or `false` only
   - Account info (username) is OK; tokens are not

---

## Production Readiness Gates

**Before claiming PRODUCTION READY:**

- [ ] All secrets removed from committed code
- [ ] All credentials rotated after incident/test cycle
- [ ] `.env` is in `.gitignore` (verify with `git check-ignore -v .env`)
- [ ] API credentials tested and valid (`verify_upcloud_credentials.py` → 0)
- [ ] Proof artifacts scanned (`scan_doc_secrets.py` → exit 0)
- [ ] No credentials in commit messages or PR descriptions
- [ ] CI/CD pipeline never prints secrets (check `.github/workflows/`)
- [ ] Documentation does not reference live token values

---

## If You Leaked a Secret

**Immediate actions:**

1. **Do NOT commit or push**
   - If already committed: `git reset --hard HEAD~1` (careful!)
   - If already pushed: Contact maintainer immediately

2. **Revoke the credential immediately**
   - UpCloud: Log in → Account → Authentication → Regenerate token
   - Upstash: Dashboard → Tokens → Regenerate
   - Inception: Request new key from team

3. **Update `.env` with new credential**
   ```bash
   # Edit .env (never commit)
   nano .env
   
   # Verify it's not staged
   git status | grep .env || echo "✅ .env not staged"
   ```

4. **Re-run verification**
   ```bash
   python3 scripts/verify_upcloud_credentials.py
   python3 scripts/scan_doc_secrets.py
   ```

5. **Inform team** (async; not blocking)
   - Post in #security channel or private Slack
   - No need to post the revoked key itself

---

## Automated Guards

### Pre-Commit Hook (Recommended)

Add to `.git/hooks/pre-commit`:

```bash
#!/bin/bash
python3 scripts/scan_doc_secrets.py || exit 1
python3 scripts/verify_upcloud_credentials.py || exit 1
exit 0
```

Make executable:
```bash
chmod +x .git/hooks/pre-commit
```

### CI/CD Gate (Automatic)

`.github/workflows/test.yml` runs:
```yaml
- name: Security scan
  run: python3 scripts/scan_doc_secrets.py
```

This fails the build if secrets are detected.

---

## Verification Scripts

### Check Credential Validity

```bash
# UpCloud API
python3 scripts/verify_upcloud_credentials.py

# Exit code:
# 0 = credentials valid, API responsive
# 1 = credentials missing or invalid
# 2 = API unreachable
```

### Scan for Leaked Secrets

```bash
# All files
python3 scripts/scan_doc_secrets.py

# Specific file
python3 scripts/scan_doc_secrets.py docs/my_file.md

# Exit code:
# 0 = no secrets found
# 1 = secrets detected (STOP, do not commit)
```

---

## During Code Review

**Reviewers MUST check:**

- ❌ No `.env` files in diff
- ❌ No hardcoded tokens in code
- ❌ No credentials in commit messages
- ❌ No credentials in proof artifacts
- ❌ All external API calls load credentials from env
- ❌ All logs/errors are sanitized (token values redacted)

**Block merge if any of the above are violated.**

---

## Incident Response

### Template for credential leak incident

1. **When discovered:** Record timestamp
2. **What leaked:** Token type, partial value (first 8 chars only), scope
3. **Where leaked:** File path, commit, or channel
4. **Who has access:** Estimate blast radius (e.g., "GitHub Actions logs are public")
5. **Action taken:** Token revoked, new token generated, secrets rotated
6. **Follow-up:** Review process to prevent recurrence

---

## Related Documents

- [AGENTS.md §9](../AGENTS.md#9-security-rules) — Security rules
- [CLAUDE.md](../CLAUDE.md) — Contributor guidelines
- `.github/workflows/test.yml` — CI/CD pipeline security gates
- `scripts/scan_doc_secrets.py` — Automated secret scanning

## External References

- **UpCloud CLI (upctl):** https://upcloudltd.github.io/upcloud-cli/latest/
  - Installation: https://upcloudltd.github.io/upcloud-cli/latest/install/
  - Configuration: https://upcloudltd.github.io/upcloud-cli/latest/config/
  - Commands: https://upcloudltd.github.io/upcloud-cli/latest/commands/
- **UpCloud API:** https://developers.upcloud.com/

---

## Questions?

**Before working with credentials:**
1. Read this document
2. Run `verify_upcloud_credentials.py`
3. Check `.env` is in `.gitignore`
4. Review AGENTS.md §9

**If still stuck:** Ask with context, never paste credentials.

---

**Last verified:** 2026-09-28  
**Next review:** 2026-10-28 (30 days)
