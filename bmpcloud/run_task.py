import argparse
import json
import os
import socket
import subprocess
import time
from pathlib import Path

from .bounds import find_lowerbound, find_upperbound
from .check_model import check
from .graph_io import read_mtx_to_adj
from .model import CONFIGS
from .run_solver import RUNNERS
from .solve_timeout import start_task_watchdog, write_task_progress
from .timing import now, elapsed_seconds, cpu_affinity

METHODS = tuple(RUNNERS)
RESULT_SCHEMA_VERSION = 2


def atomic_write_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    tmp = path.with_suffix(path.suffix + ".tmp")

    tmp.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    os.replace(tmp, path)


def current_commit(repo_root):
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()

    except Exception:
        return None


def run_task(
    instance,
    solver_name,
    config_name,
    method,
    output,
    repo_root,
    task_timeout_s=3600,
):
    if task_timeout_s <= 0:
        raise ValueError("task_timeout_s must be > 0")

    task_id = (
        f"{Path(instance).stem}"
        f"__{config_name}"
        f"__{solver_name}"
        f"__{method}"
    )

    task_started_monotonic = time.monotonic()
    task_wall0, task_cpu0 = now()

    output = Path(output)
    progress_path = output.with_suffix(".progress.json")

    timeout_done = start_task_watchdog(
        task_timeout_s=task_timeout_s,
        task_started_monotonic=task_started_monotonic,
        progress_path=progress_path,
        metadata={
            "task_id": task_id,
            "instance": str(instance),
            "solver": solver_name,
            "method": method,
            "config": config_name,
        },
    )

    try:
        write_task_progress(
            progress_path,
            task_started_monotonic,
            task_timeout_s,
            status="PREPARING",
            task_id=task_id,
            instance=str(instance),
            solver=solver_name,
            method=method,
            config=config_name,
        )

        n, m, adj = read_mtx_to_adj(instance)
        ub = find_upperbound(n, adj)
        lb = find_lowerbound(n, adj)

        write_task_progress(
            progress_path,
            task_started_monotonic,
            task_timeout_s,
            status="SEARCHING",
            task_id=task_id,
            instance=str(instance),
            solver=solver_name,
            method=method,
            config=config_name,
            n=n,
            m=m,
            lb=lb,
            ub=ub,
        )

        status, bandwidth, model, stats = RUNNERS[method](
            n=n,
            adj=adj,
            lb=lb,
            ub=ub,
            solver_name=solver_name,
            config_name=config_name,
            task_timeout_s=task_timeout_s,
            task_started_monotonic=task_started_monotonic,
            progress_path=progress_path,
        )

        search_wall, search_cpu = elapsed_seconds(
            task_wall0,
            task_cpu0,
        )

        model_valid = None
        labels = None

        if status == "OPTIMAL":
            if model is None:
                model_valid = False
                status = "INVALID_MODEL"

            else:
                labels, model_valid = check(
                    n=n,
                    adj=adj,
                    val=bandwidth,
                    model=model,
                )

                if not model_valid:
                    status = "INVALID_MODEL"

        task_wall, task_cpu = elapsed_seconds(
            task_wall0,
            task_cpu0,
        )

        payload = {
            "result_schema_version": RESULT_SCHEMA_VERSION,
            "timeout_scope": "task",
            "task_id": task_id,
            "instance": str(instance),
            "solver": solver_name,
            "method": method,
            "config": config_name,
            "n": n,
            "m": m,
            "lb": lb,
            "ub": ub,
            "bandwidth": bandwidth,
            "status": status,
            "model_valid": model_valid,
            "labels": labels,
            "task_timeout_s": task_timeout_s,
            "search_wall_time_s": round(search_wall, 9),
            "search_cpu_time_s": round(search_cpu, 9),
            "task_wall_time_s": round(task_wall, 9),
            "task_cpu_time_s": round(task_cpu, 9),
            "cpu_affinity": cpu_affinity(),
            "hostname": socket.gethostname(),
            "git_commit": current_commit(Path(repo_root)),
            **stats,
        }

        atomic_write_json(
            output,
            payload,
        )

        progress_path.unlink(missing_ok=True)

        return payload

    finally:
        timeout_done.set()


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--instance",
        required=True,
    )

    parser.add_argument(
        "--solver",
        required=True,
        choices=[
            "cadical300",
            "cryptominisat",
        ],
    )

    parser.add_argument(
        "--method",
        required=True,
        choices=METHODS,
    )

    parser.add_argument(
        "--config",
        required=True,
        choices=sorted(CONFIGS),
    )

    parser.add_argument(
        "--output",
        required=True,
    )

    parser.add_argument(
        "--repo-root",
        default=".",
    )

    parser.add_argument(
        "--task-timeout",
        "--solve-timeout",
        dest="task_timeout",
        type=float,
        default=3600,
        help=(
            "Hard wall-clock timeout for the entire task. "
            "--solve-timeout is kept as a deprecated alias."
        ),
    )

    args = parser.parse_args()

    result = run_task(
        instance=args.instance,
        solver_name=args.solver,
        config_name=args.config,
        method=args.method,
        output=args.output,
        repo_root=Path(args.repo_root).resolve(),
        task_timeout_s=args.task_timeout,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
