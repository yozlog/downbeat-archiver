from __future__ import annotations

import argparse
import logging
import sys
import time
from calendar import monthrange
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import __version__
from .core import ARCHIVE_URL, sync_archive


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Incrementally archive DownBeat PDFs by year")
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync = subparsers.add_parser("sync", help="download every currently missing issue once")
    sync.add_argument("--output", "-o", type=Path, required=True)
    sync.add_argument("--archive-url", default=ARCHIVE_URL, help=argparse.SUPPRESS)

    schedule = subparsers.add_parser("schedule", help="sync now, then automatically every month")
    schedule.add_argument("--output", "-o", type=Path, required=True)
    schedule.add_argument("--day", type=int, default=1)
    schedule.add_argument("--hour", type=int, default=3)
    schedule.add_argument("--timezone", default="Asia/Taipei")
    schedule.add_argument("--no-run-now", action="store_true")
    return parser


def _next_run(now: datetime, day: int, hour: int) -> datetime:
    year, month = now.year, now.month
    candidate_day = min(day, monthrange(year, month)[1])
    candidate = now.replace(day=candidate_day, hour=hour, minute=0, second=0, microsecond=0)
    if candidate <= now:
        if month == 12:
            year, month = year + 1, 1
        else:
            month += 1
        candidate_day = min(day, monthrange(year, month)[1])
        candidate = candidate.replace(year=year, month=month, day=candidate_day)
    return candidate


def _run(output: Path, archive_url: str = ARCHIVE_URL) -> int:
    downloaded, skipped, failed = sync_archive(output, archive_url=archive_url)
    print(f"Done: downloaded={downloaded}, skipped={skipped}, failed={failed}")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    if args.command == "sync":
        return _run(args.output, args.archive_url)

    if not 1 <= args.day <= 28 or not 0 <= args.hour <= 23:
        raise SystemExit("--day must be 1-28 and --hour must be 0-23")
    try:
        timezone = ZoneInfo(args.timezone)
    except ZoneInfoNotFoundError as error:
        raise SystemExit(f"Unknown timezone: {args.timezone}") from error

    if not args.no_run_now:
        _run(args.output)
    while True:
        now = datetime.now(timezone)
        next_run = _next_run(now, args.day, args.hour)
        seconds = max(1, (next_run - now).total_seconds())
        print(f"Next sync: {next_run.isoformat()}", flush=True)
        time.sleep(seconds)
        _run(args.output)


if __name__ == "__main__":
    sys.exit(main())
