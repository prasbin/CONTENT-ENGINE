"""Background workers (Phase 2+).

Design rule: the job queue IS the database table (``jobs``), never an
in-memory structure. A future worker process/service will atomically
claim rows in ``queued`` status, move them through the pipeline states,
and commit progress - so jobs survive API, worker, and server restarts.

This package intentionally contains no processing code yet.
"""
