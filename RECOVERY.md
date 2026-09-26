# RECOVERY

Last updated: 2026-09-26 (Phase 0 + Phase 1, restart verification run)

## 1. Background (why this file exists)

The previous CONTENT_ENGINE repository was accidentally deleted. This
repository was rebuilt from scratch on 2026-09-26 — no old files were
found on that machine during the Phase 0 audit (the workspace was
empty), so nothing was "restored". **GitHub is now the
disaster-recovery source of truth.**

This design ensures loss cannot recur silently:

- everything needed to rebuild the app is committed to Git
- secrets and machine-local state are explicitly **not** in Git and are
  documented below
- restore is a documented, reproducible sequence of commands, verified
  by running the test suite from a clean checkout

## 2. What is in Git vs. what is external

**In Git (source of truth):**

- all backend source code (`backend/app/`) and tests (`backend/tests/`)
- scripts (`scripts/`), requirements, tool config (`pyproject.toml`)
- documentation (`README` / `ARCHITECTURE` / `ROADMAP` / `CHANGELOG` / `RECOVERY`)
- `.env.example` (template only)

**NOT in Git (must be recreated/kept separately):**

| Item | Why | How to recreate |
|------|-----|-----------------|
| `.env` | contains secrets | `copy .env.example .env`, re-enter your values |
| `data/` (SQLite DB, storage objects) | machine-local runtime state | recreated automatically on first run, or `python scripts/init_db.py`; back it up separately if it holds real jobs |
| virtualenv, `__pycache__`, logs | regenerable | `pip install -r requirements-dev.txt` |
| generated media (`.mp4`, captions) | large/regenerable | re-run the pipeline (later phases) |
| platform OAuth credentials (Phases 9–10) | secrets | only in `.env`/server keychain, never in Git |

## 3. Full restore procedure (7 steps, any Windows/Linux machine)

```bash
# 1. Clone the GitHub repository
git clone https://github.com/prasbin/CONTENT-ENGINE.git
cd CONTENT-ENGINE

# 2. Restore environment configuration
cp .env.example .env          # Windows: copy .env.example .env
#    edit .env — set CE_API_TOKEN (long random value) before any remote use.
#    everything else has safe defaults; no secrets are required for dev.

# 3. Install dependencies (Python 3.12+)
python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# 4. Initialize the database (creates data/content_engine.db + tables)
python scripts/init_db.py     # expect: Tables: jobs
                              # (also happens automatically on first server start)

# 5. Run the tests
python -m pytest -q           # expect: all passed
python -m ruff check .        # expect: All checks passed

# 6. Run the development server
#    Windows:  .\scripts\dev.ps1
#    Linux:    ./scripts/dev.sh
#    equivalent: python -m uvicorn app.main:app --app-dir backend --reload

# 7. Verify the project is working
#    open http://127.0.0.1:8000/health
#    expect JSON: {"status":"ok", ..., "database":"ok"}
```

Required local state after restore: **only `.env`** (and any real job
data you want to keep from `data/`). Nothing else is expected from the
old machine.

Path safety: relative `.env`, SQLite, and storage paths resolve against
the **repository root**, not the shell's working directory — the server
behaves the same when started from the project root, from `backend/`,
or by a service manager.

## 4. Git remote (source of truth)

| Item | Value |
|------|-------|
| remote | `origin` |
| URL | `https://github.com/prasbin/CONTENT-ENGINE.git` |
| branch | `main` (tracks `origin/main`) |

Do **not** add a second remote, force-push, or reset the history.

Workflow after every phase:

```bash
git status                  # review changes
git diff                    # inspect them
python -m pytest -q         # tests must pass
git add -A
git commit -m "feat: ..."
git push                    # GitHub keeps the recovery copy
```

If GitHub credentials stop working, fix them before assuming the push
succeeded — verify with `git ls-remote --heads origin` and compare the
commit hash with `git rev-parse HEAD`.

## 5. Restore drill (verify backups actually work)

```bash
git clone https://github.com/prasbin/CONTENT-ENGINE.git /tmp/ce-drill
cd /tmp/ce-drill
pip install -r requirements-dev.txt
python -m pytest -q
```

If the tests pass in the fresh clone, the project is recoverable. Run
this drill after every important phase.

## 6. Git identity

Repository identity is configured locally:
`prasbin <prasbin@users.noreply.github.com>` (derived from the remote
account). To use your own:

```bash
git config user.name  "Your Name"
git config user.email "you@example.com"
```

## 7. What to do if files are lost again

1. `git fetch --all && git log --oneline -10` — see what the remote has.
2. Re-clone per section 3 if the local copy is gone.
3. Lost *uncommitted* work: `git fsck --lost-found` may recover blobs.
4. Never re-create secrets from memory into committed files — keep them
   only in `.env` (ignored) or a password manager.
