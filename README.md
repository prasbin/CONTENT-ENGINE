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
| 0 | Environment audit, Git safety, recovery docs | **DONE** |
| 1 | Backend foundation: FastAPI, config, DB, jobs, health, auth, storage, providers, tests | **DONE** |
| 2 | Video acquisition (yt-dlp), DB-backed worker, retry/recovery, worker CLI | **DONE** (code + tests; FFmpeg not installed locally) |
| 3 | Transcription (faster-whisper) | **NOT IMPLEMENTED** |
| 4 | AI clip detection (Ollama) | **NOT IMPLEMENTED** |
| 5–6 | Rendering + captions (FFmpeg) | **NOT IMPLEMENTED** |
| 7 | Metadata + human review | **NOT IMPLEMENTED** |
| 8–10 | Publishing (YouTube/Instagram) | **NOT IMPLEMENTED** (manual upload only by design) |
| 11 | Remote deployment (NPR 0) | **NOT VERIFIED** |
| FE | Vite/React frontend: URL input, progress, clip cards, downloads | **DONE** (builds clean; end-to-end blocked on Phase 3–6) |

Repository: `https://github.com/prasbin/CONTENT-ENGINE.git` (branch
`main`) — the disaster-recovery source of truth; see RECOVERY.md.

Verified this run (2026-10-25):

- `python -m pytest -q` → **99 passed, 1 skipped**
- `python -m ruff check .` → **All checks passed**
- `python -m ruff format --check backend/app/models/` → **2 files already formatted**
  (4 pre-existing files elsewhere have formatting drift; left untouched to preserve existing work)
- Frontend `npm run build` → **built in ~2.7s, 0 errors** (150 kB JS / 6.6 kB CSS gzipped)
- Restored missing `backend/app/models/` package (`Job`, `JobStatus`, `can_transition`, `PIPELINE_ORDER`) that the existing services, schemas, and tests import but was absent from disk

Not verified / blocked in this environment:
- FFmpeg / ffprobe not installed → no media probing or rendering
- faster-whisper / Ollama not installed → no transcription or AI clip detection
- No live backend request exercised (dev server cannot run in this sandbox)
- No end-to-end job (URL → three rendered clips) was run
- No production deployment (NPR 0 hosting not yet selected)
- Docker, APK build, YouTube/Instagram publishing: not applicable here

The frontend builds and its API client matches the real FastAPI routes,
but it cannot produce real clips until Phase 3–6 are implemented.

## Requirements

- Python 3.12+ (tested: 3.13.5 on Linux; backend is Linux-compatible)
- Node.js 18+ and npm (for the frontend)
- Git (for version control/recovery)
- Optional, for full pipeline: FFmpeg (ffprobe), faster-whisper, Ollama

```bash
pip install -r requirements-dev.txt   # runtime + test/lint deps
cd frontend && npm install             # frontend deps
```

## Quickstart

```bash
# 1. configure (never commit .env)
cp .env.example .env

# 2. initialize the database (optional - also happens on first server start)
python scripts/init_db.py

# 3. run the API (http://127.0.0.1:8000, docs at /docs)
./scripts/dev.sh
# equivalent: python -m uvicorn app.main:app --app-dir backend --reload

# 4. run tests + lint
./scripts/test.sh
# equivalent: python -m pytest -q && python -m ruff check .
```

### Frontend (Vite + React)

```bash
cd frontend
cp .env.example .env      # optional: set VITE_API_BASE_URL for production
npm install
npm run dev               # http://localhost:5173
npm run build             # production build into frontend/dist/
```

In development the Vite dev server proxies `/api` to the FastAPI backend
at `http://127.0.0.1:8000` (configurable via `VITE_API_BASE_URL`). Run
the backend and frontend in two terminals. The UI polls the job status
every 2 seconds and shows progress through the pipeline stages.

Relative config/database/storage paths resolve against the repository
root, so the server behaves identically regardless of the working
directory it is started from.

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

Frontend variables (in `frontend/.env`):

| Variable | Default | Meaning |
|----------|---------|---------|
| `VITE_API_BASE_URL` | *(empty)* | Base URL of the FastAPI backend. Empty in dev uses the Vite proxy. |
| `VITE_API_TOKEN` | *(empty)* | Bearer token matching `CE_API_TOKEN` (same-origin deployments only). |

Invalid configuration fails fast with a message naming the exact
variable (e.g. `invalid configuration -> CE_PORT: Input should be...`).

## Project tree

```
CONTENT ENGINE/
├── .env.example          # config template (real .env is git-ignored)
├── .gitignore            # secrets, data, media, build outputs excluded
├── README.md  ARCHITECTURE.md  ROADMAP.md  CHANGELOG.md  RECOVERY.md
├── requirements.txt  requirements-dev.txt  pyproject.toml
├── scripts/              # dev/test scripts + init_db.py + worker.py
├── backend/
│   ├── app/
│   │   ├── main.py       # FastAPI factory + lifespan (DB init)
│   │   ├── api/          # deps (auth/DI), v1 routes (health, jobs)
│   │   ├── core/         # config, paths, logging+redaction, errors, security
│   │   ├── db/           # SQLAlchemy base + engine/session helpers
│   │   ├── models/       # Job + JobStatus + transition rules
│   │   ├── schemas/      # Pydantic request/response models
│   │   ├── services/     # JobService (only write path to jobs table)
│   │   ├── providers/    # pipeline interfaces + yt-dlp source + media probe
│   │   ├── storage/      # StorageProvider protocol + LocalStorage
│   │   └── workers/      # AcquisitionWorker (DB-backed queue)
│   └── tests/            # 99 behavioral tests
└── frontend/             # Vite + React UI
    ├── src/              # App, api client, types, stages, clips
    └── public/           # favicon, PWA manifest
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
- **Working-directory independent**: `.env`, SQLite files, and storage
  paths resolve against the repository root (tested), so Linux service
  managers or odd CWDs cannot silently redirect data or miss config.
- **No fake functionality**: the frontend never displays simulated clips.
  Clip cards show a placeholder until a real `download_url` is present in
  the job payload; previews and download buttons are wired to real backend
  output URLs only.

## Current limitations (honest)

- **No transcription, AI clip selection, or rendering yet.** Submitting a
  URL creates a job, but the pipeline stops after acquisition. The frontend
  will show progress through `downloading` then report that clips are not
  available. This is intentional, not a bug.
- **FFmpeg is required** for media validation, rendering, and caption
  burning. It is not installed in this environment.
- **No production deployment.** NPR 0 hosting for long-running Python
  video workers is not yet selected. The app is not independently
  deployable yet.
- **Manual upload only.** Automatic YouTube/Instagram publishing is
  intentionally out of scope; the user downloads MP4s and uploads them.

## Remaining acceptance criteria

The project is **not** complete. To meet the full directive, the next
work is: implement Phase 3 (faster-whisper transcription), Phase 4 (AI
clip detection producing 20s/30s/35s candidates), Phase 5–6 (FFmpeg
rendering + burned-in captions with exact durations), a download
endpoint, and a verified NPR 0 deployment target.

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
