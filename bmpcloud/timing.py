from __future__ import annotations

import os
import time


def now():
    return time.perf_counter_ns(), time.process_time_ns()


def elapsed_seconds(start_wall_ns, start_cpu_ns):
    wall_ns = time.perf_counter_ns() - start_wall_ns
    cpu_ns = time.process_time_ns() - start_cpu_ns
    return wall_ns / 1_000_000_000.0, cpu_ns / 1_000_000_000.0


def cpu_affinity():
    if hasattr(os, "sched_getaffinity"):
        try:
            return sorted(os.sched_getaffinity(0))
        except Exception:
            pass
    return None
