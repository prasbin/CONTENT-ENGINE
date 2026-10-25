"""Acquisition worker CLI script.

Usage:
  python scripts/worker.py run [--once] [--poll SECONDS]
  python scripts/worker.py recover
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
from app.providers.factory import build_storage, build_video_source_provider  # noqa: E402
from app.services.jobs import JobService  # noqa: E402
from app.workers.acquisition import AcquisitionWorker  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="CONTENT ENGINE Acquisition Worker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run command
    run_parser = subparsers.add_parser(
        "run",
        help="Run the acquisition worker loop",
    )
    run_parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one job then exit",
    )
    run_parser.add_argument(
        "--poll",
        type=float,
        default=2.0,
        help="Polling interval in seconds when idle",
    )
    run_parser.add_argument(
        "--max-jobs",
        type=int,
        default=None,
        help="Stop after processing N jobs",
    )

    # recover command
    subparsers.add_parser("recover", help="Requeue jobs interrupted while downloading")

    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.ce_log_level, json_logs=settings.is_production)

    engine = create_engine_from_url(settings.ce_database_url)
    init_db(engine)
    session_factory = create_session_factory(engine)
    job_service = JobService(session_factory)
    storage = build_storage(settings)
    provider = build_video_source_provider(settings, storage)
    worker = AcquisitionWorker(job_service=job_service, provider=provider, settings=settings)

    if args.command == "recover":
        requeued = worker.recover_interrupted()
        print(f"Requeued {len(requeued)} downloading job(s): {requeued}")
        sys.exit(0)

    elif args.command == "run":
        max_jobs = 1 if args.once else args.max_jobs
        worker.run(max_jobs=max_jobs, poll_seconds=args.poll)
        sys.exit(0)


if __name__ == "__main__":
    main()
