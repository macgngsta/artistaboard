"""CLI: preview / paint a job, or run the scheduler daemon.

python -m vestaboard preview <job>     # render to terminal, never touch the board
python -m vestaboard paint <job>       # render once and send to the board
python -m vestaboard run               # daemon: paint ACTIVE_JOB on its schedule
"""

from __future__ import annotations

import argparse
import logging
import sys

from .client import VestaboardClient
from .config import get_settings
from .preview import render_preview
from .registry import JOB_TYPES, build_job

log = logging.getLogger("vestaboard")


def _preview(job_name: str) -> int:
    settings = get_settings()
    job = build_job(job_name, settings)
    scene = job.build()
    print(render_preview(scene.to_characters()))
    return 0


def _paint(job_name: str) -> int:
    settings = get_settings()
    job = build_job(job_name, settings)
    scene = job.build()
    print(render_preview(scene.to_characters()))
    with VestaboardClient(settings.vestaboard_rw_key) as client:
        result = client.send(scene.to_characters())
    log.info("painted %s: %s", job_name, result)
    return 0


def _run() -> int:
    from apscheduler.schedulers.blocking import BlockingScheduler

    settings = get_settings()
    job = build_job(settings.active_job, settings)
    client = VestaboardClient(settings.vestaboard_rw_key)

    def tick() -> None:
        try:
            job.paint(client)
            log.info("painted %s", job.name)
        except Exception:
            log.exception("job %s failed", job.name)

    scheduler = BlockingScheduler()
    scheduler.add_job(tick, "interval", seconds=job.interval_seconds, next_run_time=None)
    tick()  # paint immediately on startup
    log.info("scheduled %s every %ss", job.name, job.interval_seconds)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        client.close()
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # httpx logs each request URL at INFO; the 511 endpoint carries the api_key as a
    # query param, so keep it at WARNING to avoid leaking the key into logs.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(prog="vestaboard")
    sub = parser.add_subparsers(dest="command", required=True)

    job_names = sorted(JOB_TYPES)
    p_preview = sub.add_parser("preview", help="render a job to the terminal")
    p_preview.add_argument("job", choices=job_names)
    p_paint = sub.add_parser("paint", help="render a job once and send to the board")
    p_paint.add_argument("job", choices=job_names)
    sub.add_parser("run", help="run the scheduler daemon for ACTIVE_JOB")

    args = parser.parse_args(argv)
    if args.command == "preview":
        return _preview(args.job)
    if args.command == "paint":
        return _paint(args.job)
    return _run()


if __name__ == "__main__":
    sys.exit(main())
