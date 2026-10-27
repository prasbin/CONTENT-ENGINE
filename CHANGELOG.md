# CHANGELOG

All notable changes to CONTENT ENGINE are documented here.
Format: [version] — date (newest first).

## [0.3.1] - 2026-10-27

Hardening and real-media verification pass over the Phase 2-6 pipeline
that landed in `b63358b`..`ff9fc35` (frontend, Colab notebook,
`PipelineWorker`, transcription/clip-detection/render/caption
providers). Audited rather than rebuilt; three real bugs found and
fixed, verified against real speech audio.

### Fixed

- `clip_detection.py`: **every real run crashed** with `TypeError`
  (`[0.0] * int(duration) + 1` evaluates as list + int). The 9 existing
  tests passed only because none exercised a transcript long enough to
  reach that code path.
- `clip_detection.py`: `target_duration` labels were mispaired with
  clip windows after chronological sort (a 30s window could be
  reported as the 20s clip). Windows are now paired with their target
  before sorting.
- `clip_detection.py`: greedy selection could strand leftover gaps too
  small for a remaining clip (failed to fit a 35s clip in a real
  ~110s transcript). Added `_select_windows` backtracking over target
  orderings (largest-first, then permutations).
- `transcription.py`: VAD-silence (all audio filtered) leaked the
  internal `ValueError: max() iterable argument is empty`; now maps to
  a clear "no speech detected in the source media" error.
- `workers/acquisition.py`, `workers/pipeline.py`, `scripts/worker.py`:
  `--once` CLI mode polled forever on an empty queue; both workers now
  accept `stop_when_idle` and exit cleanly.
- `workers/pipeline.py`, `services/jobs.py`, `core/config.py`: pipeline
  claims now use a dedicated `pipeline_attempts` counter with a cap
  (`CE_MAX_PIPELINE_ATTEMPTS`, default 3) enforced in `run_once` —
  previously a crash/recover loop for one job ran forever.
- `pyproject.toml`: ruff now excludes `notebooks/` (46 lint errors all
  lived in the Colab notebook; app code was already clean).

### Added

- `tests/test_clip_detection_long_transcript.py` (3): exact
  non-overlapping 20/30/35s clips on a 120s synthetic transcript;
  honest refusal at 50s; empty-transcript refusal.
- `tests/test_pipeline_hardening.py` (3): attempts cap, VAD silence
  message, CLI `--once` exits on empty queue.
- `tests/test_real_media_pipeline.py` (2, REAL media): Windows SAPI
  ~105s speech -> real faster-whisper `tiny`/int8/CPU -> transcript
  containing the spoken content, then real `HeuristicClipDetector`
  -> three exact, non-overlapping 20/30/35s clips. Skips honestly when
  SAPI or the whisper model is unavailable.

### Verification

- 117 passed, 1 skipped (`test_render_integration.py` — FFmpeg absent),
  ruff clean, pytest exit 0.
- Real end-to-end: SAPI speech -> whisper -> clip detection verified on
  this machine. Rendering (Phases 5/6) remains **blocked** on FFmpeg:
  `FFmpegRenderer` is implemented and fails honestly
  (`RendererUnavailable`) without it.

## [0.1.1] - 2026-09-26

Restart verification run (Phase 0 re-audit + Phase 1 improvements).
Repository was audited first: the Phase 0/1 foundation from `045ec57`
was present, tested (71 passed), lint-clean, and free of secrets, so it
was **reused and improved** rather than replaced.

### Changed

- New `app/core/paths.py`: `.env`, SQLite, and storage paths now resolve
  against the **repository root** instead of the process working
  directory — the server behaves identically when started from the
  project root, from `backend/`, or by a Linux service manager
  (verified live: server started from `backend/` created the database at
  the repository root, not `backend/data/`).
- `app/core/config.py`: loads the project `.env` by absolute path
  (CWD-independent).
- `app/db/session.py`: `normalize_database_url()` anchors relative
  SQLite paths at the repository root; absolute paths, `:memory:`, and
  non-SQLite URLs unchanged.
- `app/main.py`: storage root resolved through `project_path()`.

### Added

- `scripts/init_db.py` — explicit database initialization without
  starting the server (recovery step 4); exit code 0/1, works from any
  working directory.
- 12 new tests (71 → **83**): path anchoring, CWD independence,
  project-root `.env` loading behavior, storage/DB path normalization,
  init script success + invalid-config failure (subprocess).
- `RECOVERY.md` rewritten around the live GitHub remote: 7-step restore
  procedure with the real clone URL, remote table, push workflow, and
  restore drill.

### Verified this run

- `python -m pytest -q` → 83 passed
- `python -m ruff check .` / `ruff format --check .` → clean
- `python scripts/init_db.py` → `Tables: jobs`
- live `GET /health` → `status=ok, database=ok` (server started from
  `backend/` CWD)

## [0.1.0] — 2026-09-26

First rebuild of the repository after the previous one was lost
(Phase 0 + Phase 1 only).

### Added — Phase 0 (safety net)

- Fresh Git repository initialized in the project directory.
- `.gitignore` excluding secrets (`.env`), databases, generated media,
  model files, node/Android build outputs, logs.
- `.env.example` documenting every configuration variable.
- `README.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `RECOVERY.md`.
- Development scripts: `scripts/dev.ps1|sh`, `scripts/test.ps1|sh`.

### Added — Phase 1 (backend foundation)

- FastAPI application factory (`create_app`) with lifespan-managed
  database startup and shutdown.
- Typed environment configuration (`app/core/config.py`) with
  Pydantic-Settings, `CE_*` variables, CORS parsing, and fail-fast
  `ConfigurationError` messages naming the offending variable.
- SQLAlchemy 2.0 models + session helpers; SQLite default via
  `CE_DATABASE_URL` (PostgreSQL-ready).
- Persistent `jobs` table (UUID id, source_url, status, progress,
  error_message, payload, timestamps) with tested status-transition
  rules (`queued … published`, `failed` retry, `published` terminal).
- Job service + versioned API: `POST/GET/PATCH /api/v1/jobs`,
  `GET /health` and `GET /api/v1/health`.
- Error envelope `{"error": {code, message, details?}}` with handlers
  for domain, validation, HTTP, and unhandled errors.
- Authentication abstraction: `AuthProvider` protocol,
  `TokenAuthProvider` (constant-time compare), `AllowAllAuthProvider`
  for development, bearer-token dependency on all job routes.
- Storage abstraction: `StorageProvider` protocol + `LocalStorage`
  with path-traversal protection.
- Provider interfaces for later phases: `VideoSourceProvider`,
  `TranscriptionProvider`, `ClipDetectionProvider`, `Renderer`,
  `CaptionProvider`, `MetadataProvider`, `Publisher`; registry that
  raises `ProviderNotConfiguredError` (501) with the phase hint.
- Structured logging with JSON formatter and secret-redaction filter.
- 71 pytest tests covering startup, health, config, database
  persistence across restarts, jobs API, auth, storage, providers,
  logging redaction, and error shapes.
- Ruff lint/format configuration and clean run.

### Security

- No secrets committed; `.env` git-ignored; `.env.example` contains
  placeholders only.
- Production warning logged when `APP_ENV=production` without a token.
