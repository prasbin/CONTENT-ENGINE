# CHANGELOG

All notable changes to CONTENT ENGINE are documented here.
Format: [version] — date.

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
