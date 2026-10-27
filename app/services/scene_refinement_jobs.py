"""Bounded in-memory quality passes. No image files, no extra inference.

Opaque capabilities expire after completion. Photos live only in the running
closure; completed jobs retain JSON alone. Single-worker deployment, like QR.
"""

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from secrets import token_urlsafe
from threading import Event, Lock
from time import monotonic
from typing import Any

_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="scene-quality")
_lock = Lock()
_jobs: dict[str, tuple[float, Future[dict[str, Any]], Event]] = {}
_active: set[Future[dict[str, Any]]] = set()
MAX_JOBS = 2
TTL_SECONDS = 180


def _clean() -> None:
    now = monotonic()
    for token, (expires, job, _abandoned) in list(_jobs.items()):
        if expires < now and job.done():
            del _jobs[token]


def submit(work: Callable[[], dict[str, Any]]) -> str | None:
    with _lock:
        _clean()
        _active.difference_update([job for job in _active if job.done()])
        if len(_jobs) >= MAX_JOBS or len(_active) >= MAX_JOBS:
            return None
        token = token_urlsafe(24)
        abandoned = Event()

        def execute() -> dict[str, Any]:
            return {} if abandoned.is_set() else work()

        job = _pool.submit(execute)
        _active.add(job)
        _jobs[token] = (monotonic() + TTL_SECONDS, job, abandoned)
        return token


def snapshot(token: str) -> dict[str, Any] | None:
    with _lock:
        _clean()
        entry = _jobs.get(token)
    if entry is None:
        return None
    job = entry[1]
    if not job.done():
        return {"status": "pending"}
    try:
        return {"status": "ready", "experimental": job.result()}
    except Exception:
        # Never expose filenames, arrays or exception details to the client.
        return {"status": "failed"}


def discard(token: str) -> None:
    with _lock:
        entry = _jobs.pop(token, None)
    if entry:
        # A running call cannot be cancelled safely inside OpenCV. Keep it
        # counted until completion. Queued abandoned work skips refinement;
        # repeated photo changes cannot build an unbounded array-holding queue.
        entry[2].set()
