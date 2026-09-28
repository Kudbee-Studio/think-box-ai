# PR 271 — Security Hardening & Incident Remediation

**Date:** 2026-09-27  
**Severity:** CRITICAL + HIGH  
**Status:** IN PROGRESS

---

## Incident Summary

On 2026-09-28, a critical security incident was discovered via laptop scan:

1. **CRITICAL-1: SSH Private Key Exposed in Git**
   - File: `kilo-upcloud-recovered` (Ed25519 SSH private key)
   - Committed: 2026-09-24 in commit `9f12e1dd`
   - Status: Publicly visible on `https://github.com/Kudbee-Studio/think-box-ai`
   - Impact: Any GitHub access = can clone private repos / SSH to UpCloud

2. **CRITICAL-2: Agent OS Dashboard Listening on All Interfaces**
   - Status: ✅ **FIXED in commit dd1b525**
   - Fixed: Changed binding from `0.0.0.0:3000` → `127.0.0.1:3000`

---

## PR 271 Remediation Steps

### Phase 1: Remove SSH Key from Git History (IN PROGRESS)

**Status:** Running `git filter-branch` to remove `kilo-upcloud-recovered` from all commits.

```bash
cd /tmp/think-box-ai-purge
git filter-branch --tree-filter 'rm -f kilo-upcloud-recovered kilo-upcloud-recovered.pub' -- --all
git reflog expire --expire=now --all
git gc --prune=now
```

**Expected Output:**
- Rewrites all commits containing the key
- Reflog cleaned
- Repository gc'd (reduced size)

### Phase 2: Force-Push Cleaned History

After filter-branch completes:

```bash
cd /tmp/think-box-ai-purge
git push origin --force-with-lease --all
git push origin --force-with-lease --tags
```

**Note:** This is a DESTRUCTIVE operation. All team members must rebase.

### Phase 3: Local Cleanup

```bash
cd /home/domin/projects/think-box-ai
rm -f kilo-upcloud-recovered kilo-upcloud-recovered.pub
git reflog expire --expire=now --all
git gc --prune=now
```

### Phase 4: WSL Environment Hardening

Run on WSL machine (ASAP):

```bash
# Fix .env permissions
chmod 600 .env

# Verify
ls -la .env  # Should show: -rw------- (600)

# Rotate all exposed API keys
# Files: INCEPTION_API_KEY, UPSTASH_VECTOR_REST_TOKEN, Cursor keys
vi .env  # Regenerate all tokens
```

### Phase 5: Windows PostgreSQL Hardening

On Windows PostgreSQL 18:

1. Edit: `C:\Program Files\PostgreSQL\18\data\postgresql.conf`
2. Find `listen_addresses` and change:
   ```ini
   # Before:
   listen_addresses = '*'
   
   # After:
   listen_addresses = 'localhost'
   ```
3. Restart PostgreSQL service
4. Verify: `netstat -an | findstr 5432` should show `127.0.0.1:5432`

---

## Files Changed

| File | Change | Status |
|------|--------|--------|
| Git history | Remove `kilo-upcloud-recovered` | 🔄 IN PROGRESS |
| `.gitignore` | Add SSH key patterns | ✅ DONE (commit dd1b525) |
| `apps/web/server.ts` | Bind to 127.0.0.1 | ✅ DONE (commit dd1b525) |
| `.env` (WSL) | chmod 600 | ⏳ PENDING |
| `postgresql.conf` (Windows) | listen_addresses localhost | ⏳ PENDING |

---

## Verification Checklist

After all phases complete:

- [ ] Git history purged: `git log --all --full-history -- kilo-upcloud-recovered | wc -l` = 0
- [ ] Force-push to origin/main completed
- [ ] All team members rebased
- [ ] .env permissions fixed: `ls -la .env | grep "rw-------"`
- [ ] API keys rotated in Inception, Upstash, Cursor
- [ ] PostgreSQL listens on localhost only
- [ ] Dashboard accessible only from `127.0.0.1:3000`
- [ ] UpCloud SSH key revoked (founder action)

---

## Team Notifications

**Required Actions:**
1. Founder: Revoke UpCloud SSH key immediately
2. All team: Pull and rebase after force-push
3. WSL machines: Run chmod 600 .env
4. Windows machines: Update PostgreSQL config

---

## Timeline

| Action | Owner | Target |
|--------|-------|--------|
| Remove from git history | Claude | Today |
| Force-push to main | Founder | Today |
| Notify team | Founder | Today |
| Revoke UpCloud key | Founder | Today |
| Fix WSL .env | Team | Today |
| Fix PostgreSQL | Team | Today |

---

**Status:** CRITICAL — Do not deploy until SSH key is purged and team has rebased.
