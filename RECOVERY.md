# RECOVERY

Last updated: 2026-09-26 (Phase 0 + Phase 1)

## 1. Background (why this file exists)

The previous CONTENT_ENGINE repository was accidentally deleted. This
repository was **rebuilt from scratch** on 2026-09-26 — nothing was
"restored" from the old project, and no old files were found on this
machine during the Phase 0 audit (the workspace directory was empty).
If the old code ever reappears, treat it as a reference, not as truth.

This rebuild is designed so that loss cannot happen again:

- everything needed to rebuild the app is committed to Git
- secrets and machine-local state are explicitly **not** in Git and are
  documented below
- restore is a documented, reproducible sequence of commands

## 2. What is in Git vs. what is external

**In Git (source of truth):**

- all backend/frontend/mobile source code
- tests, requirements, scripts, tool config (`pyproject.toml`)
- documentation (`README/ARCHITECTURE/ROADMAP/CHANGELOG/RECOVERY`)
- `.env.example` (template only)

**NOT in Git (must be recreated/kept separately):**

| Item | Why | How to recreate |
|------|-----|-----------------|
| `.env` | contains secrets | `copy .env.example .env` then re-enter your values |
| `data/` (SQLite DB, storage objects) | machine-local runtime state | recreated automatically on first run; back up separately if you have real jobs |
| virtualenv, `__pycache__`, logs | regenerable | `pip install -r requirements-dev.txt` |
| generated media (`.mp4`, captions) | large/regenerable | re-run the pipeline |
| platform OAuth credentials (Phases 9–10) | secrets | stored only in `.env`/server keychain, never in Git |

## 3. Full restore procedure (any Windows/Linux machine)

```bash
# 1. Get the code (use your remote once configured, see section 4)
git clone <YOUR_REPOSITORY_URL> content-engine
cd content-engine

# 2. Python environment (3.12+)
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 3. Configuration
cp .env.example .env             # Windows: copy .env.example .env
#    edit .env - set CE_API_TOKEN (long random value) before any remote use

# 4. Verify the rebuild
python -m pytest -q              # expect: all tests passed
python -m ruff check .           # expect: All checks passed

# 5. Run
python -m uvicorn app.main:app --app-dir backend --reload
#    open http://127.0.0.1:8000/health  -> status "ok"
```

Required local state after restore: **only `.env`**. Nothing else is
expected from the old machine.

## 4. Git remote (important)

This repository was initialized **without a remote** (none existed; none
was invented). Until you push to a remote, your code exists only on this
machine — that is exactly how the previous project was lost.

Add a remote and push (create an empty repository on GitHub/GitLab/etc.
first):

```bash
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

Then update the clone URL in section 3. Recommended backup: push after
every phase, plus an occasional fresh clone test (section 5).

## 5. Restore drill (verify your backups actually work)

```bash
git clone <YOUR_REPOSITORY_URL> /tmp/ce-drill
cd /tmp/ce-drill
pip install -r requirements-dev.txt
python -m pytest -q
```

If the tests pass in the fresh clone, the project is recoverable.

## 6. Git identity used for the initial commit

The machine had no Git `user.name`/`user.email` configured, so the
repository uses a local identity derived from the existing GitHub remote
found on this machine. To use your own identity:

```bash
git config user.name  "Your Name"
git config user.email "you@example.com"
# future commits will use it; past authorship can be rewritten with care
```

## 7. What to do if files are lost again

1. `git log --oneline` — check what commits exist locally.
2. `git fetch --all` — pull from the remote if configured.
3. Lost uncommitted work: `git fsck --lost-found` may recover blobs.
4. Follow section 3 to rebuild the environment from the repository.
5. Never re-create secrets from memory into committed files — keep them
   only in `.env` (ignored) or a password manager.
