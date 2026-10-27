# ROADMAP

Status legend: **DONE** = implemented *and* verified with tests this run;
**NOT STARTED** = not implemented; **BLOCKED** = waiting on environment
or user action.

| Phase | Scope | Status | Notes |
|------:|-------|--------|-------|
| 0 | Environment audit, Git safety net, recovery docs | **DONE** | Repo + GitHub remote; `.gitignore`; RECOVERY.md (7-step restore) |
| 1 | Backend foundation: FastAPI app, config, DB, job model, health, auth, storage, provider interfaces, tests | **DONE** | 83 tests pass; ruff clean; CWD-independent paths; init_db script; live server verified |
| 2 | Video acquisition: URL validation, download, source verification, source metadata | **DONE** | yt-dlp Python API; size/timeout caps; DB worker + crash recovery (`d2aab2f`) |
| 3 | Transcription: speech-to-text, timestamped segments, persisted transcript | **DONE** | faster-whisper (free/offline/CPU int8, VAD); REAL-verified: SAPI speech → transcript via pipeline worker |
| 4 | AI clip detection: strong moments (motivation, mindset, gym, podcasts, informative) | **DONE** | Heuristic scorer (density + hooks + backtracking exact-window fit); REAL-verified: 3 exact non-overlapping 20/30/35s clips from real transcript; honest refusal when source too short |
| 5 | Short rendering: vertical 9:16, 1080×1920, H.264/AAC, safe framing | **BLOCKED** | Implemented (`FFmpegRenderer`, honest `RendererUnavailable`); **FFmpeg not installed on this machine** — render integration test skips until it is |
| 6 | Captions: burned-in, timestamp-aligned, mobile-readable, safe margins | **BLOCKED** | Implemented (ASS burn-in via renderer); verification blocked by the same missing FFmpeg |
| 7 | Metadata + human review: title/description/hashtags, editable, approve/reject gate | NOT STARTED | Approval gate is mandatory before any publishing |
| 8 | Publishing abstractions: `Publisher` contract, credential storage | NOT STARTED | Official APIs only |
| 9 | YouTube Shorts publishing | NOT STARTED | Requires Google OAuth + YouTube Data API verification (user action) |
| 10 | Instagram Reels publishing | NOT STARTED | Requires Meta app review + Graph API (user action) |
| 11 | Remote/server deployment | NOT STARTED | BLOCKED: $0 budget, no card → evaluate free tiers/VPS/home host; HTTPS + reverse proxy |
| 12 | Android APK (Capacitor): server URL, token, submit/status/preview/approve/publish | NOT STARTED | Android SDK present; Gradle not on PATH (wrapper can fetch) |
| 13 | True phone-only E2E: URL → approval → published, laptop off | NOT STARTED | Depends on 2–12 |
| 14 | Reliability: backups, monitoring, restart-safe workers, hardening | NOT STARTED | |
| 15 | Content launch / earning workflow | NOT STARTED | No income claims; rights/monetization remain the user's responsibility |

## Upcoming decisions (need user input before Phase 11+)

1. **Compute host** for the backend (free-tier trial, home machine, or
   cheap VPS) — application is already provider-agnostic.
2. **Transcription engine** (local Whisper vs API) — affects Phase 3 cost/latency.
3. **Platform accounts** — Google Cloud project (YouTube) and Meta app
   (Instagram) must be created and verified by the user (Phase 9/10).

## Exit criteria philosophy

A phase is "DONE" only when its tests/commands were actually run and
recorded. Nothing is marked complete on paper.
