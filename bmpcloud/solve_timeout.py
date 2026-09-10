from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

TIMEOUT_EXIT_CODE = 124
_progress_lock = threading.Lock()


def _atomic_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def _read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def task_timing(task_started_monotonic: float, task_timeout_s: float):
    elapsed = max(0.0, time.monotonic() - task_started_monotonic)
    remaining = max(0.0, task_timeout_s - elapsed)
    return round(elapsed, 6), round(remaining, 6)


def write_task_progress(
    progress_path,
    task_started_monotonic: float,
    task_timeout_s: float,
    *,
    status: str,
    **metadata,
):
    if not progress_path:
        return

    progress = Path(progress_path)
    elapsed, remaining = task_timing(
        task_started_monotonic,
        task_timeout_s,
    )

    payload = {
        **metadata,
        "status": status,
        "timeout_scope": "task",
        "task_timeout_s": task_timeout_s,
        "task_elapsed_s": elapsed,
        "task_remaining_s": remaining,
    }

    with _progress_lock:
        _atomic_json(progress, payload)


def start_task_watchdog(
    task_timeout_s: float,
    task_started_monotonic: float,
    progress_path=None,
    metadata=None,
):
    if task_timeout_s <= 0:
        raise ValueError("task_timeout_s must be > 0")

    done = threading.Event()
    progress = Path(progress_path) if progress_path else None
    base_metadata = dict(metadata or {})

    def watchdog():
        elapsed = time.monotonic() - task_started_monotonic
        remaining = max(0.0, task_timeout_s - elapsed)

        if done.wait(remaining):
            return

        if progress:
            with _progress_lock:
                current = _read_json(progress)
                timeout_payload = {
                    **base_metadata,
                    **current,
                    "status": "TIMEOUT",
                    "timeout_scope": "task",
                    "task_timeout_s": task_timeout_s,
                    "task_elapsed_s": round(
                        time.monotonic() - task_started_monotonic,
                        6,
                    ),
                    "task_remaining_s": 0.0,
                    "timeout_source": "task_watchdog",
                }
                _atomic_json(progress, timeout_payload)

        os._exit(TIMEOUT_EXIT_CODE)

    threading.Thread(
        target=watchdog,
        name="task-timeout-watchdog",
        daemon=True,
    ).start()

    return done
