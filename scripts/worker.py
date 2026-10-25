"""Worker CLI script: acquisition and pipeline workers.

Usage:
  python scripts/worker.py run [--once] [--poll SECONDS] [--max-jobs N]
  python scripts/worker.py recover
  python scripts/worker.py pipeline run [--once] [--poll SECONDS] [--max-jobs N]
  python scripts/worker.py pipeline recover
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure backend package is on sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402
from app.db.session import (  # noqa: E402
    create_engine_from_url,
    create_session_factory,
    init_db,
)
from app.providers.factory import (  # noqa: E402
    build_pipeline_worker,
    build_storage,
    build_video_source_provider,
)
from app.services.jobs import JobService  # noqa: E402
from app.workers.acquisition import AcquisitionWorker  # noqa: E402


def _add_run_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--once", action="store_true", help="Process at most one job then exit")
    p.add_argument("--poll", type=float, default=None, help="Polling interval in seconds when idle")
    p.add_argument("--max-jobs", type=int, default=None, help="Stop after processing N jobs")


def main() -> None:
    parser = argparse.ArgumentParser(description="CONTENT ENGINE Worker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the acquisition worker loop")
    _add_run_args(run_parser)
    subparsers.add_parser("recover", help="Requeue jobs interrupted while downloading")

    pipe_parser = subparsers.add_parser(
        "pipeline", help="Run the transcription->render pipeline worker"
    )
    pipe_sub = pipe_parser.add_subparsers(dest="pipe_command", required=True)
    prun = pipe_sub.add_parser("run", help="Run the pipeline worker loop")
    _add_run_args(prun)
    pipe_sub.add_parser("recover", help="Requeue jobs interrupted mid-pipeline")

    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.ce_log_level, json_logs=settings.is_production)

    engine = create_engine_from_url(settings.ce_database_url)
    init_db(engine)
    session_factory = create_session_factory(engine)
    job_service = JobService(session_factory)
    storage = build_storage(settings)

    if args.command == "pipeline":
        worker = build_pipeline_worker(settings, job_service, storage)
        if args.pipe_command == "recover":
            requeued = worker.recover_interrupted()
            print(f"Requeued {len(requeued)} pipeline job(s): {requeued}")
            sys.exit(0)
        elif args.pipe_command == "run":
            max_jobs = 1 if args.once else args.max_jobs
            poll = args.poll if args.poll is not None else settings.ce_worker_poll_seconds
            worker.run(max_jobs=max_jobs, poll_seconds=poll)
            sys.exit(0)

    provider = build_video_source_provider(settings, storage)
    worker = AcquisitionWorker(job_service=job_service, provider=provider, settings=settings)

    if args.command == "recover":
        requeued = worker.recover_interrupted()
        print(f"Requeued {len(requeued)} downloading job(s): {requeued}")
        sys.exit(0)
    elif args.command == "run":
        max_jobs = 1 if args.once else args.max_jobs
        poll = args.poll if args.poll is not None else settings.ce_worker_poll_seconds
        worker.run(max_jobs=max_jobs, poll_seconds=poll)
        sys.exit(0)


if __name__ == "__main__":
    main()
