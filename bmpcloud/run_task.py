import argparse
import json
import os
import socket
import subprocess
from pathlib import Path

from .bounds import find_lowerbound, find_upperbound
from .check_model import check
from .graph_io import read_mtx_to_adj
from .model import CONFIGS
from .run_solver import RUNNERS
from .timing import now, elapsed_seconds, cpu_affinity

METHODS = tuple(RUNNERS)


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
    solve_timeout_s=3000,
):
    task_wall0, task_cpu0 = now()

    output = Path(output)
    progress_path = output.with_suffix(".progress.json")

    n, m, adj = read_mtx_to_adj(instance)
    ub = find_upperbound(n, adj)
    lb = find_lowerbound(n, adj)

    # Run task that will find result
    status, bandwidth, model, stats = RUNNERS[method](
        n=n,
        adj=adj,
        lb=lb,
        ub=ub,
        solver_name=solver_name,
        config_name=config_name,
        solve_timeout_s=solve_timeout_s,
        progress_path=progress_path,
    )

    # Stop counting time that we won't add check time to the total time.
    task_wall, task_cpu = elapsed_seconds(
        task_wall0,
        task_cpu0,
    )

    # Check result from model if find optimal solution.
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

   # Load result to metadata

    payload = {
        "task_id": (
            f"{Path(instance).stem}"
            f"__{config_name}"
            f"__{solver_name}"
            f"__{method}"
        ),

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
        "solve_timeout_s": solve_timeout_s,
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
        "--solve-timeout",
        type=float,
        default=3000,
    )

    args = parser.parse_args()

    result = run_task(
        instance=args.instance,
        solver_name=args.solver,
        config_name=args.config,
        method=args.method,
        output=args.output,
        repo_root=Path(args.repo_root).resolve(),
        solve_timeout_s=args.solve_timeout,
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
