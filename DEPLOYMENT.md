# Deployment Guide

This guide covers deploying Content Engine to a free Python hosting provider
(e.g. Enzonic). The application consists of two independently-run processes
that share a database and storage directory.

## Architecture

```
┌─────────────────────────────────┐     ┌──────────────────────────────┐
│  API process (FastAPI/uvicorn)  │     │  Worker process (Python CLI)  │
│  - Serves REST API + frontend   │     │  - Acquisition (yt-dlp)       │
│  - Health endpoint              │     │  - Transcription (Whisper)    │
│  - Does NOT run workers         │     │  - Clip detection + rendering │
│  - Does NOT load Whisper model  │     │    (FFmpeg)                   │
└────────────┬────────────────────┘     └──────────────┬───────────────┘
             │                                         │
             └──────────┬──────────────────────────────┘
                        │
              ┌─────────▼──────────┐
              │  SQLite database   │
              │  + file storage    │
              │  (shared paths)    │
              └────────────────────┘
```

## Prerequisites

1. **Python 3.12+**
2. **FFmpeg** (with libx264, aac, libass filters) — required only on the
   worker process for video rendering
3. **ffprobe** — required for media validation (optional via
   `CE_REQUIRE_MEDIA_PROBE=false`)
4. **pip packages**: `pip install -r requirements.txt`

## Environment variables

Copy `.env.example` to `.env` and fill in the values.

| Variable | Default | Description |
|---|---|---|
| `APP_ENV` | `development` | Set to `production` for deployment |
| `CE_HOST` | `127.0.0.1` | Bind address; use `0.0.0.0` for hosting |
| `CE_PORT` | `8000` | Port the API listens on |
| `CE_DATABASE_URL` | `sqlite:///./data/content_engine.db` | SQLAlchemy database URL |
| `CE_STORAGE_PATH` | `./data/storage` | Directory for source videos and rendered clips |
| `CE_API_TOKEN` | _(empty = auth disabled)_ | Bearer token for API authentication |
| `CE_PUBLIC_BASE_URL` | _(empty)_ | Public URL of the API (e.g. `https://yourapp.example.com`). Used to generate download URLs for rendered clips. |
| `CE_CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins. Set to your deployed frontend URL. Do NOT use `*` with credentials. |
| `CE_LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL` |
| `CE_MAX_SOURCE_BYTES` | `524288000` (500 MB) | Max download size per source video |
| `CE_DOWNLOAD_TIMEOUT_SECONDS` | `300` | Download timeout per source |
| `CE_REQUIRE_MEDIA_PROBE` | `true` | Set to `false` if ffprobe is unavailable |
| `CE_FFMPEG_PATH` | `ffmpeg` | Path to FFmpeg binary |
| `CE_FFPROBE_PATH` | `ffprobe` | Path to ffprobe binary |
| `CE_WHISPER_MODEL` | `tiny` | Whisper model size (see below) |
| `CE_WHISPER_DEVICE` | `cpu` | `cpu` or `cuda` |
| `CE_WHISPER_COMPUTE_TYPE` | `int8` | `int8`, `int8_float16`, `float16`, `float32` |
| `CE_MAX_STORAGE_BYTES` | `10737418240` (10 GB) | Total storage limit before rejecting new downloads |
| `CE_WORKER_POLL_SECONDS` | `2.0` | How often the worker polls for new jobs |
| `CE_TEMP_CLEANUP_ENABLED` | `true` | Whether to clean up temp files after processing |

## Whisper model options

| Model | Size | RAM | Quality | Speed |
|---|---|---|---|---|
| `tiny` | ~75 MB | ~500 MB | Low | Fastest |
| `base` | ~145 MB | ~600 MB | Low-medium | Fast |
| `small` | ~488 MB | ~1 GB | Medium | Moderate |

For free/low-memory hosting, use `tiny` with `int8` compute type. The model
downloads from HuggingFace on first use and is cached under `~/.cache`.

## Startup commands

### API server

```bash
# Development (auto-reload):
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --reload

# Production:
APP_ENV=production python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000
```

### Worker processes

```bash
# Acquisition worker (downloads source videos):
python scripts/worker.py run

# Pipeline worker (transcription -> clip detection -> rendering):
python scripts/worker.py pipeline run

# Process a single job then exit (useful for cron/queue-based hosting):
python scripts/worker.py run --once
python scripts/worker.py pipeline run --once

# Recover interrupted jobs:
python scripts/worker.py recover
python scripts/worker.py pipeline recover
```

### Frontend

```bash
cd frontend
npm install
npm run build  # outputs to frontend/dist/
```

The built static files in `frontend/dist/` can be served by any static file
host or by the API itself (if configured).

Set `VITE_API_BASE_URL` at build time to point at the deployed backend:

```bash
VITE_API_BASE_URL=https://yourapi.example.com npm run build
```

## Health check

```bash
curl https://yourapi.example.com/health
```

Returns `{"status": "ok", "service": "content-engine", "database": "ok", ...}`.
This endpoint does NOT load Whisper or perform any video processing — it only
checks database connectivity. Safe for load balancer health checks.

## Storage and persistence

**Important**: SQLite database files, source videos, and rendered clips are
stored on the local filesystem. They persist **only if the hosting provider
supplies persistent storage**. If the hosting provider uses ephemeral
containers (files reset on restart), all data is lost on restart.

- Database: `CE_DATABASE_URL` points to a SQLite file (default:
  `./data/content_engine.db`)
- Source videos and clips: `CE_STORAGE_PATH` (default: `./data/storage`)
- Temp files: FFmpeg and the downloader use `tempfile.TemporaryDirectory()`
  which auto-cleans on context exit
- Whisper model cache: `~/.cache/huggingface/` (downloaded on first use)

For persistent storage on hosting providers that support it, mount a
persistent volume at `./data/` and set both `CE_DATABASE_URL` and
`CE_STORAGE_PATH` to paths within that volume.

## Resource limits

- **Max source download**: `CE_MAX_SOURCE_BYTES` (default 500 MB)
- **Download timeout**: `CE_DOWNLOAD_TIMEOUT_SECONDS` (default 300s)
- **Max acquisition retries**: `CE_MAX_ACQUISITION_ATTEMPTS` (default 3)
- **Total storage cap**: `CE_MAX_STORAGE_BYTES` (default 10 GB) — new
  downloads are rejected if storing would exceed this limit
- **Worker poll interval**: `CE_WORKER_POLL_SECONDS` (default 2s) — higher
  values reduce CPU usage when idle

## API and worker independence

The API process and worker process are designed to run independently:

- They share the same SQLite database and storage directory (via
  `CE_DATABASE_URL` and `CE_STORAGE_PATH`)
- The API process does NOT start any worker threads
- The API process does NOT load the Whisper model at startup
- The worker process does NOT serve HTTP requests
- Job claiming uses atomic compare-and-swap updates to prevent duplicate
  processing when multiple workers run
- Interrupted jobs are recovered on worker startup via `recover_interrupted()`

## Security

- Set `CE_API_TOKEN` to a strong random string in production
- Set `CE_CORS_ORIGINS` to your exact frontend origin(s) — do not use `*`
  with credentials
- In production (`APP_ENV=production`), unhandled exception tracebacks are
  NOT logged to avoid leaking filesystem paths; only the exception type is
  logged
- Source URLs are validated: only `http`/`https` schemes, no embedded
  credentials, max 4096 characters
- Storage paths reject `..` traversal, absolute paths, and drive letters

## Enzonic-specific notes

Enzonic's free Python hosting provides a queuing system for server
allocation. The following cannot be confirmed without access to the Enzonic
server panel:

1. **Persistent storage**: Whether the allocated server has persistent disk
   storage or resets on restart. Check the Enzonic dashboard for volume
   mount options.
2. **Background processes**: Whether the platform allows running a
   long-lived worker process alongside the API, or only supports
   request-triggered execution. If only request-triggered, use
   `python scripts/worker.py run --once` and `python scripts/worker.py
   pipeline run --once` as cron jobs or webhook triggers.
3. **FFmpeg availability**: Whether FFmpeg/ffprobe are pre-installed. If
   not, use the `imageio-ffmpeg` Python package for the ffmpeg binary
   (bundled, no system install needed). ffprobe must be installed separately.
4. **Memory limits**: Free tiers typically have 256-512 MB RAM. The `tiny`
   Whisper model with `int8` compute type fits in ~500 MB. Rendering
   (FFmpeg) may require additional memory for large videos.
5. **Port binding**: Whether the platform expects the app to bind to a
   specific port (often via a `PORT` environment variable). Set `CE_PORT`
   accordingly.
