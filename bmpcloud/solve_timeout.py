from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

TIMEOUT_EXIT_CODE = 124


def _atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def solve_with_hard_timeout(
    solver,
    timeout_s: float,
    assumptions=None,
    progress_path=None,
    metadata=None,
):
    """Apply a hard wall-clock timeout to one solver.solve() call."""
    if timeout_s <= 0:
        return solver.solve(assumptions=assumptions or [])

    done = threading.Event()
    progress = Path(progress_path) if progress_path else None
    meta = dict(metadata or {})
    started = time.monotonic()

    if progress:
        _atomic_json(progress, {
            **meta,
            "status": "SOLVING",
            "solve_timeout_s": timeout_s,
        })

    def watchdog():
        if done.wait(timeout_s):
            return

        if progress:
            _atomic_json(progress, {
                **meta,
                "status": "TIMEOUT",
                "solve_timeout_s": timeout_s,
                "solve_elapsed_s": round(time.monotonic() - started, 6),
            })

        # Each experiment is already an independent OS process.
        # Exiting here kills only this task, leaving the batch scheduler alive.
        os._exit(TIMEOUT_EXIT_CODE)

    threading.Thread(
        target=watchdog,
        name="sat-solve-watchdog",
        daemon=True,
    ).start()

    try:
        return solver.solve(assumptions=assumptions or [])
    finally:
        done.set()
