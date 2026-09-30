# SECURITY CHECKLIST — kudbEE Agent OS

**Purpose:** Every agent session MUST run this checklist before committing code or accessing production systems.

**Last updated:** 2026-09-29  
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

`upctl` is a **Go binary**. It is **not** on PyPI: `pip install upcloud-cli` fails, because
PyPI returns 404 for that project. The install methods below come from the official
docs (`UpCloudLtd/upcloud-cli`, `docs/index.md`); last checked 2026-09-29 against
release v3.36.0.

```bash
# Install (one-time). Ubuntu/Debian: .deb from GitHub releases
VER=3.36.0   # latest: https://github.com/UpCloudLtd/upcloud-cli/releases
curl -Lo upcloud-cli_${VER}_amd64.deb \
  https://github.com/UpCloudLtd/upcloud-cli/releases/download/v${VER}/upcloud-cli_${VER}_amd64.deb
# Verify against checksums.txt from the same release, then:
sudo apt install ./upcloud-cli_${VER}_amd64.deb
# No root? Use upcloud-cli_${VER}_linux_x86_64.tar.gz from the same release
# (verify with checksums.txt), extract `upctl`, and put it on PATH.
# macOS: brew tap UpCloudLtd/tap && brew install upcloud-cli
# From source: go install github.com/UpCloudLtd/upcloud-cli/v3/...@latest
upctl version

# Authenticate: upctl reads UPCLOUD_TOKEN, the system keyring, or ~/.config/upctl.yaml.
# The verify script passes THINKBOX_UPCLOUD_API_TOKEN to upctl as UPCLOUD_TOKEN if
# UPCLOUD_TOKEN is unset, so no extra setup is needed.
# To store a token in the keyring instead:
upctl account login --with-token

# Verify in future sessions
python3 scripts/verify_upcloud_cli.py            # add --install for install help
# Exit code: 0 = ready, 1 = not installed, 2 = not authenticated

# Or test directly with the CLI
upctl account show       # Account username, credits, limits
upctl server list        # Servers in *this token's* account (see Accounts below)
```

> **Two UpCloud accounts.** `THINKBOX_UPCLOUD_API_TOKEN` authenticates as account
> `kudbeex`, which holds the active worker `kudbee-hermes-worker-02`
> (`00e300f7-4fc9-49cf-af9b-b11c79f76853`, `209.50.51.174`). `UPCLOUD_API_KEY`
> authenticates as account `kudbee`, which holds `kudbee-hermes-worker-01`. A server
> in the other account returns `SERVER_FORBIDDEN`, not `SERVER_NOT_FOUND`. Always
> check which account you're in (`upctl account show`) before acting, and address
> servers by UUID: hostnames are not unique.

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

**Recommendation:** Use `upctl` for interactive and operational work. It is UpCloud's official CLI. Use `scripts/verify_upcloud_credentials.py` (stdlib HTTP, no install) when upctl is not available.

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
| `THINKBOX_UPCLOUD_API_TOKEN` | UpCloud API, account `kudbeex` (active worker-02) | **Full account access**: it has created and deleted servers. Treat it as write-capable, not read-only. | 90 days |
| `UPCLOUD_API_KEY` | UpCloud API, account `kudbee` (worker-01 only) | Full account access; a separate account from `kudbeex` | 90 days |
| `UPCLOUD_SERVER_IP` / `UPCLOUD_SERVER_HOSTNAME` / `UPCLOUD_SSH_USER` / `UPCLOUD_SSH_KEY_PATH` | Worker SSH target (read by `thinkbox/upcloud.py` `UpCloudConfig`) | A key **path** only. Never put private-key contents in env or code. | On key rotation |
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

---

## Dashboard and remote-execution boundaries (updated 2026-09-30)

**Dashboard: local-only, no user authentication (login was tried in #285/#286 and deliberately deferred).**
The server binds to `127.0.0.1` and refuses any other `LISTEN_ADDR` unless `KUDBEE_ALLOW_NON_LOOPBACK=1`.
Do not expose it. User authentication (and HTTPS) is a **required** step before any remote or shared use.

Boundaries that remain, each fail-closed:

1. **Backend API key** (`THINKBOX_API_KEY`), never sent to the browser.
2. **Governance admission** (`thinkbox/admission.py`): valid token, right agent, capability held by the
   identity **and** present in the token. The dashboard token carries only `shell:upcloud-ssh:readonly`
   and lasts 300s.
3. **Execution policy** (`thinkbox/remote_exec_policy.py`): `upcloud-ssh` requires that capability, the
   capability allows only `upcloud-ssh`, and the command must exactly match one of six read-only commands.
4. **Admission binding** (`thinkbox/execution_authorization.py`): what `POST /run` authorized is
   persisted immutably; resume and reclaim may only run exactly that, and resume needs a token too.
5. **`/api/git`**: public `https://github.com` clones only, no shell, files confined to the workspace.
6. **Local-only request gate** (`apps/web/server.ts`, 2026-09-30). A loopback bind alone doesn't stop
   a web page in the operator's browser: WebSocket upgrades ignore same-origin policy, and DNS
   rebinding points an attacker's hostname at 127.0.0.1. So:
   - every HTTP request must carry a loopback `Host` on the dashboard port (else 421);
   - every WebSocket upgrade also needs `Origin` = `http://{127.0.0.1|localhost|[::1]}:<port>` (else
     401). A missing Origin is refused unless `DASHBOARD_ALLOW_NO_ORIGIN=1`.
7. **Operator plugins:**
   - `shell_exec` is disabled unless `DASHBOARD_ENABLE_SHELL_EXEC=1`, and then still needs approval.
   - `plugin_execute`/`git_action` calls that execute, write, clone or send a non-GET request wait for
     a human `approval_response`.
   - `file_read`/`file_write` are confined to the session workspace (no absolute paths, `..`, or
     escaping symlinks).
   - Plugins act only on the caller's own session.

Residual (accepted for local-only use):
- a local process on this machine can forge `Origin`;
- an accepted socket can start `run_goal` runs that spend model tokens.

Never expose to the browser: `THINKBOX_API_KEY`, governance tokens, or SSH/UpCloud credentials.

## External References

- **UpCloud CLI (upctl):** https://upcloudltd.github.io/upcloud-cli/latest/ (getting started: install + credentials)
  - Source and releases (binaries, `checksums.txt`): https://github.com/UpCloudLtd/upcloud-cli/releases
  - (The earlier `/latest/install/`, `/latest/config/` and `/latest/commands/` links returned 404 on 2026-09-29 and were removed.)
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

**Last verified:** 2026-09-29 (upctl section live-checked against v3.36.0)  
**Next review:** 2026-10-28 (30 days)
