# CONTENT ENGINE

Automated short-video content system: **BUILD → LEARN → EARN → SCALE**.

Paste a YouTube/video URL → transcribe → AI finds strong short moments →
render vertical 9:16 short → captions → title/description/hashtags →
**human approval** → publish to YouTube Shorts / Instagram Reels.

**Control from an Android phone.** Heavy processing runs on a remote
server, never inside the APK. The laptop is only for development.

## Current status (honest)

| Phase | Scope | Status |
|-------|-------|--------|
| 0 | Environment audit, Git safety, recovery docs | **DONE** (verified this run) |
| 1 | Backend foundation: FastAPI, config, DB, jobs, health, auth, storage, providers, tests | **DONE** (verified this run) |
| 2+ | Download, transcription, AI, rendering, captions, publishing, deployment, APK | **NOT IMPLEMENTED** |

Verified in this run:

- `python -m pytest -q` → **71 passed**
- `python -m ruff check .` → **All checks passed**; `ruff format --check .` → 40 files formatted
- Live server started (`uvicorn app.main:app`), `GET /health` returned
  `status=ok, database=ok`; with `CE_API_TOKEN` set, `GET /api/v1/jobs`
  returned **401** without a token and **200** with a valid token;
  `POST /api/v1/jobs` created a real job.

Not verified (blocked/not applicable in this environment): Docker (not
installed), FFmpeg (not installed), Ollama (not installed), cloud
deployment (no account/budget), APK build, YouTube/Instagram publishing.
See ROADMAP.md and the final Phase 0/1 report.

## Requirements

- Python 3.12+ (tested: 3.12.10 on Windows 10/11; backend is Linux-compatible)
- Git (for version control/recovery)

```powershell
pip install -r requirements-dev.txt   # runtime + test/lint deps
```

## Quickstart

```powershell
# 1. configure (never commit .env)
copy .env.example .env

# 2. run the API (http://127.0.0.1:8000, docs at /docs)
.\scripts\dev.ps1
# equivalent: python -m uvicorn app.main:app --app-dir backend --reload

# 3. run tests
.\scripts\test.ps1
# equivalent: python -m pytest -q
```

Linux/macOS: `./scripts/dev.sh`, `./scripts/test.sh`.

## API (v1)

Base path: `/api/v1`. Errors always look like
`{"error": {"code": "...", "message": "...", "details": ...}}`.

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | `/health` | no | Liveness + DB check |
| GET | `/api/v1/health` | no | Same, versioned |
| POST | `/api/v1/jobs` | yes | Create job from a video URL |
| GET | `/api/v1/jobs` | yes | List jobs (`limit`, `offset`, `status`) |
| GET | `/api/v1/jobs/{id}` | yes | Job detail |
| PATCH | `/api/v1/jobs/{id}` | yes | Update status/progress/error/payload |
| GET | `/openapi.json`, `/docs` | no | Interactive API docs |

"Auth = yes" only when `CE_API_TOKEN` is set. In development with no
token the API is open and logs a warning. Production **must** set a token.

## Configuration

Copy `.env.example` → `.env`. All values come from the environment:

| Variable | Default | Meaning |
|----------|---------|---------|
| `APP_ENV` | `development` | `development\|testing\|staging\|production` |
| `CE_HOST` / `CE_PORT` | `127.0.0.1` / `8000` | HTTP listener |
| `CE_DATABASE_URL` | `sqlite:///./data/content_engine.db` | Any SQLAlchemy URL (PostgreSQL later) |
| `CE_STORAGE_PATH` | `./data/storage` | Local object storage root |
| `CE_API_TOKEN` | *(empty)* | Bearer token; empty = dev-only open API |
| `CE_PUBLIC_BASE_URL` | *(empty)* | Public URL after deployment |
| `CE_CORS_ORIGINS` | localhost Vite ports | Comma-separated origins |
| `CE_OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Future AI inference endpoint |
| `CE_LOG_LEVEL` | `INFO` | `DEBUG\|INFO\|WARNING\|ERROR\|CRITICAL` |

Invalid configuration fails fast with a message naming the exact
variable (e.g. `invalid configuration -> CE_PORT: Input should be...`).

## Project tree

```
CONTENT ENGINE/
├── .env.example          # config template (real .env is git-ignored)
├── .gitignore            # secrets, data, media, build outputs excluded
├── README.md  ARCHITECTURE.md  ROADMAP.md  CHANGELOG.md  RECOVERY.md
├── requirements.txt  requirements-dev.txt  pyproject.toml
├── scripts/              # dev.ps1, dev.sh, test.ps1, test.sh
└── backend/
    ├── app/
    │   ├── main.py       # FastAPI factory + lifespan (DB init)
    │   ├── api/          # deps (auth/DI), v1 routes (health, jobs)
    │   ├── core/         # config, logging+redaction, errors, security
    │   ├── db/           # SQLAlchemy base + engine/session helpers
    │   ├── models/       # Job + JobStatus + transition rules
    │   ├── schemas/      # Pydantic request/response models
    │   ├── services/     # JobService (only write path to jobs table)
    │   ├── providers/    # pipeline interfaces + registry (DI)
    │   ├── storage/      # StorageProvider protocol + LocalStorage
    │   └── workers/      # documented placeholder (Phase 2+, DB-backed)
    └── tests/            # 71 behavioral tests
```

## Design highlights

- **Jobs are rows in the database**, never in-memory — they survive API,
  worker, and server restarts (tested).
- **Provider interfaces** (`VideoSourceProvider`, `TranscriptionProvider`,
  `ClipDetectionProvider`, `Renderer`, `CaptionProvider`,
  `MetadataProvider`, `Publisher`, `StorageProvider`) are ready for later
  phases; unconfigured ones fail loudly with the phase that will provide
  them.
- **Infrastructure-agnostic**: no cloud provider hard-coded; SQLite now,
  any SQLAlchemy DB later; local storage now, remote object storage later.
- **No fake functionality**: only Phase 1 features exist. No download,
  transcription, rendering, or publishing code is present yet.

## Content rights disclaimer

This system can technically process third-party videos. That does **not**
grant rights to reuse, monetize, or redistribute them. You are
responsible for permissions, copyright, and platform monetization
eligibility. Nothing here guarantees income or monetization.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) — layers, job lifecycle, provider map
- [ROADMAP.md](ROADMAP.md) — phases 0–15 and current status
- [RECOVERY.md](RECOVERY.md) — how to restore this project from Git
- [CHANGELOG.md](CHANGELOG.md) — what changed per version
