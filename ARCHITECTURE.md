# ARCHITECTURE

Last updated: 2026-09-26 (Phase 0 + Phase 1)

## 1. System shape

```
┌─────────────────────┐        HTTPS (production)        ┌──────────────────────────────┐
│  Android APK        │ ───────────────────────────────► │  BACKEND (remote server)      │
│  (control client)   │   submit URL, poll jobs,         │  FastAPI + workers            │
│  Capacitor          │   preview, edit metadata,        │  acquisition → transcription  │
│  NO FFmpeg/AI/DB    │   approve/reject, publish        │  → AI clips → render →        │
└─────────────────────┘                                  │    captions → metadata →      │
                                                         │    review → publish           │
        ┌──────────────────────┐                         └───────────┬──────────────────┘
        │  Dev laptop          │                                    │
        │  Windows (this repo) │                                    ▼
        │  dev/test/commit only│                    ┌──────────────────────────────┐
        └──────────────────────┘                    │  DB + STORAGE                 │
                                                    │  SQLite now / PostgreSQL later│
                                                    │  local FS now / object store  │
                                                    └──────────────────────────────┘
```

Rules that are already enforced by the code:

- The APK never runs Python, FFmpeg, Ollama, or a database; it only
  calls the backend API.
- The laptop is not required for production operation; jobs live in the
  database on the server.
- No in-memory job queue: `jobs` table is the source of truth.
- No cloud provider is hard-coded anywhere; infrastructure decisions are
  isolated from application code.

## 2. Backend layers

```
backend/app/
├── api/          HTTP layer: routes, DI wiring, auth enforcement
│   ├── deps.py       get_settings/get_storage/get_job_service/require_auth
│   └── v1/           versioned routes (health, jobs) + router.py
├── core/         cross-cutting: config, errors, logging, security
├── db/           engine/session factory, declarative base, init_db
├── models/       ORM: Job, JobStatus, transition rules
├── schemas/      Pydantic request/response contracts
├── services/     business logic (JobService) — the only jobs-table writer
├── providers/    pipeline interfaces + ProviderRegistry (DI)
├── storage/      StorageProvider protocol + LocalStorage
└── workers/      Phase 2+ (DB-backed queue; intentionally empty code now)
```

Dependency direction: `api → services → models/db`, with `core` and
`providers` used across layers. Routes never touch SQLAlchemy directly.

Request flow:

```
HTTP → FastAPI route (auth via AuthProvider)
     → JobService (validation, status transitions, commits)
     → SQLAlchemy Session → SQLite/PostgreSQL
     → Pydantic response schema → JSON
```

Startup flow (`lifespan`): create engine → `init_db` (create_all) →
session factory → `JobService` → on shutdown, dispose engine.
Construction (`create_app`) performs no filesystem/database I/O, which
keeps tests hermetic.

## 3. Job model

Table `jobs`:

| Column | Type | Notes |
|--------|------|-------|
| `id` | string(36) PK | UUID4 (portable to PostgreSQL) |
| `source_url` | text | sanitized http(s) URL, no embedded credentials |
| `status` | string(32), indexed | see lifecycle below |
| `progress` | int 0–100 | |
| `error_message` | text nullable | set when failing |
| `payload` | JSON | job config/metadata (niche, language, ...) |
| `created_at` / `updated_at` | timestamptz-style | `updated_at` auto-refreshes on update |

Lifecycle states (persisted as strings):

```
queued → downloading → transcribing → analyzing → rendering → captioning
      → metadata → review → approved → publishing → published
any non-published state → failed ; failed → queued (retry only)
```

Transition rules (`app/models/job.py::can_transition`, unit-tested):

- same status: always allowed
- `failed`: reachable from any non-published status; leaves only to `queued`
- `published`: terminal
- forward: exactly one stage at a time (no skipping)
- backward: allowed for re-work (e.g. `review → rendering`)

Persistence guarantee: state lives in the DB, so API/worker/server
restarts do not lose jobs (covered by tests that reopen the engine and
by a two-app-instance API test).

## 4. Provider abstraction (infrastructure swap points)

| Provider name | Interface (`app/providers/base.py`) | Phase |
|---|---|---|
| `storage` | `StorageProvider` → `LocalStorage` **(implemented)** | 1 |
| `video_source` | `VideoSourceProvider` | 2 |
| `transcription` | `TranscriptionProvider` | 3 |
| `clip_detection` | `ClipDetectionProvider` | 4 |
| `renderer` | `Renderer` (FFmpeg behind the interface) | 5 |
| `captions` | `CaptionProvider` | 6 |
| `metadata` | `MetadataProvider` | 7 |
| `publishers` | `Publisher` (YouTube, Instagram) | 8–10 |

`ProviderRegistry.get(name)` raises `ProviderNotConfiguredError` (HTTP
501) naming the phase that will provide it — missing capabilities are
loud, never silent stubs. Implementations are swapped by registering a
different object; route code does not change.

External boundaries that can be re-pointed without code changes:

- **Database**: `CE_DATABASE_URL` (SQLite → PostgreSQL = URL + migration)
- **Storage**: `StorageProvider` protocol (local FS → S3-compatible)
- **AI inference**: `CE_OLLAMA_BASE_URL` (Ollama-compatible endpoint)
- **Auth**: `AuthProvider` protocol (static token now; JWT/OAuth later)
- **Publishing**: `Publisher` protocol (official platform APIs only)

## 5. API conventions

- Versioned prefix `/api/v1`; `/health` unversioned for probes.
- Stable error envelope: `{"error": {"code", "message", "details?"}}`.
  Codes: `not_found`, `unauthorized`, `validation_error`,
  `invalid_status_transition`, `provider_not_configured`,
  `invalid_storage_path`, `internal_error`, ...
- Auth: `Authorization: Bearer <CE_API_TOKEN>` via `AuthProvider`;
  constant-time comparison; health endpoints stay open.
- CORS: origins from `CE_CORS_ORIGINS`.
- Docs: `/openapi.json` + `/docs`.

## 6. Configuration & security

- All config from environment / `.env` (git-ignored); typed and
  validated by Pydantic; failures name the offending variable.
- **Path anchoring**: `.env`, relative SQLite files, and relative
  storage paths resolve against the repository root
  (`app/core/paths.py`), never the process working directory — required
  for predictable behavior under Linux service managers and for
  identical Windows/Linux development.
- Secrets never hard-coded; logs pass through a redaction filter
  (`token/password/secret/api_key/authorization/bearer` values masked).
- Storage names reject absolute paths, drive letters, and `..` (path
  traversal defense).
- Source URLs restricted to http(s), length-capped, no embedded
  credentials.
- Production TODOs (later phases): HTTPS behind reverse proxy, signed
  media URLs, upload/download limits, token rotation, rate limiting.

## 7. Deliberate non-goals for Phase 1

- No Alembic migrations yet (`create_all` is the Phase 1 foundation;
  migrations arrive before schema changes matter).
- No worker process yet (DB-backed claim loop comes with Phase 2).
- No Docker/Compose (not available in this environment — untested).
- No microservices: one FastAPI app, modular monolith, extractable later.
