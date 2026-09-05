import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from .model import CONFIGS
from .run_task import METHODS
from .solve_timeout import TIMEOUT_EXIT_CODE


def parse_selection(values, allowed):
    if values == ["all"]:
        return list(allowed)

    unknown = sorted(set(values) - set(allowed))
    if unknown:
        raise SystemExit(f"Unknown values: {unknown}")

    return values


def completed(path):
    if not path.exists():
        return False

    try:
        result = json.loads(path.read_text(encoding="utf-8"))
        return result.get("status") in {
            "OPTIMAL",
            "UNSAT",
            "TIMEOUT",
        }
    except Exception:
        return False


def atomic_json(path, payload):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp, path)


def write_tables(run_dir):
    result_paths = sorted((run_dir / "results").glob("*.json"))
    task_rows = []
    solve_rows = []

    for path in result_paths:
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        solve_records = row.pop("solve_records", [])

        if isinstance(row.get("cpu_affinity"), list):
            row["cpu_affinity"] = ",".join(map(str, row["cpu_affinity"]))

        task_rows.append(row)

        for record in solve_records:
            solve_rows.append({
                "task_id": row.get("task_id"),
                "instance": row.get("instance"),
                "config": row.get("config"),
                "solver": row.get("solver"),
                "method": row.get("method"),
                **record,
            })

    if task_rows:
        fields = sorted({k for row in task_rows for k in row})
        tmp = run_dir / "summary.csv.tmp"
        out = run_dir / "summary.csv"

        with tmp.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in sorted(task_rows, key=lambda r: r.get("task_id", "")):
                writer.writerow(row)

        os.replace(tmp, out)

    if solve_rows:
        fields = sorted({k for row in solve_rows for k in row})
        tmp = run_dir / "solve_details.csv.tmp"
        out = run_dir / "solve_details.csv"

        with tmp.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in solve_rows:
                writer.writerow(row)

        os.replace(tmp, out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".")
    p.add_argument("--testcase-dir", default="testcase")
    p.add_argument("--run-dir", required=True)

    p.add_argument(
        "--solvers",
        nargs="+",
        default=["cadical300", "cryptominisat"],
    )
    p.add_argument(
        "--methods",
        nargs="+",
        default=["repeated", "incremental", "assumption"],
    )
    p.add_argument("--configs", nargs="+", default=["all"])

    p.add_argument(
        "--solve-timeout",
        type=float,
        default=3000,
        help="Timeout for each individual SAT solve() call.",
    )

    p.add_argument(
        "--cpu-core",
        type=int,
        default=1,
        help="Pin every SAT task to this single logical CPU. Use 0 on a 1-vCPU VM.",
    )

    p.add_argument(
        "--settle-seconds",
        type=float,
        default=1.0,
        help="Fixed quiet delay between tasks; excluded from task timing.",
    )

    args = p.parse_args()

    repo_root = Path(args.repo_root).resolve()
    testcase_dir = (repo_root / args.testcase_dir).resolve()
    run_dir = Path(args.run_dir).resolve()
    result_dir = run_dir / "results"
    log_dir = run_dir / "logs"

    result_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)

    cpu_count = os.cpu_count() or 1
    if not 0 <= args.cpu_core < cpu_count:
        raise SystemExit(
            f"--cpu-core={args.cpu_core} is invalid; VM exposes {cpu_count} CPUs."
        )

    configs = parse_selection(args.configs, sorted(CONFIGS))
    solvers = parse_selection(
        args.solvers,
        ["cadical300", "cryptominisat"],
    )
    methods = parse_selection(args.methods, METHODS)

    tasks = []

    for instance in sorted(testcase_dir.rglob("*.mtx")):
        for config in configs:
            for solver in solvers:
                for method in methods:
                    task_id = (
                        f"{instance.stem}"
                        f"__{config}"
                        f"__{solver}"
                        f"__{method}"
                    )

                    output = result_dir / f"{task_id}.json"
                    progress = result_dir / f"{task_id}.progress.json"

                    if not completed(output):
                        tasks.append(
                            (
                                task_id,
                                instance,
                                config,
                                solver,
                                method,
                                output,
                                progress,
                            )
                        )

    print(
        "TIMING MODE | jobs=1 | "
        f"pending={len(tasks)} | "
        f"cpu_core={args.cpu_core} | "
        f"timeout_per_solve={args.solve_timeout}s | "
    )

    child_env = os.environ.copy()
    child_env["OMP_NUM_THREADS"] = "1"
    child_env["OPENBLAS_NUM_THREADS"] = "1"
    child_env["MKL_NUM_THREADS"] = "1"
    child_env["NUMEXPR_NUM_THREADS"] = "1"
    child_env["PYTHONHASHSEED"] = "0"

    total = len(tasks)

    for index, task in enumerate(tasks, start=1):
        (
            task_id,
            instance,
            config,
            solver,
            method,
            output,
            progress,
        ) = task

        cmd = [
            "taskset",
            "-c",
            str(args.cpu_core),
            sys.executable,
            "-m",
            "bmpcloud.run_task",
            "--instance",
            str(instance),
            "--solver",
            solver,
            "--method",
            method,
            "--config",
            config,
            "--output",
            str(output),
            "--repo-root",
            str(repo_root),
            "--solve-timeout",
            str(args.solve_timeout),
        ]

        out_path = log_dir / f"{task_id}.out.log"
        err_path = log_dir / f"{task_id}.err.log"

        print(f"[{index}/{total}] START {task_id}")

        with out_path.open("w", encoding="utf-8") as stdout_handle, \
             err_path.open("w", encoding="utf-8") as stderr_handle:

            proc = subprocess.Popen(
                cmd,
                cwd=repo_root,
                stdout=stdout_handle,
                stderr=stderr_handle,
                env=child_env,
                start_new_session=True,
            )

            # STRICTLY sequential: do not start the next task before this one exits.
            rc = proc.wait()

        if rc == TIMEOUT_EXIT_CODE:
            progress_data = {}

            if progress.exists():
                try:
                    progress_data = json.loads(
                        progress.read_text(encoding="utf-8")
                    )
                except Exception:
                    progress_data = {}

            atomic_json(output, {
                "task_id": task_id,
                **progress_data,
                "status": "TIMEOUT",
                "solve_timeout_s": args.solve_timeout,
                "timing_mode": "single_job",
                "cpu_core": args.cpu_core,
            })

            print(
                f"[{index}/{total}] TIMEOUT {task_id} "
                f"at bandwidth={progress_data.get('bandwidth_check')}"
            )

        elif rc != 0 and not output.exists():
            atomic_json(output, {
                "task_id": task_id,
                "status": "ERROR",
                "returncode": rc,
                "timing_mode": "single_job",
                "cpu_core": args.cpu_core,
            })

            print(f"[{index}/{total}] ERROR rc={rc} {task_id}")

        else:
            # Add scheduler metadata without modifying the timing measurements.
            try:
                data = json.loads(output.read_text(encoding="utf-8"))
                data["timing_mode"] = "single_job"
                data["cpu_core"] = args.cpu_core
                atomic_json(output, data)
            except Exception:
                pass

            print(f"[{index}/{total}] DONE {task_id}")

        progress.unlink(missing_ok=True)
        write_tables(run_dir)

        if args.settle_seconds > 0 and index < total:
            time.sleep(args.settle_seconds)

    write_tables(run_dir)


if __name__ == "__main__":
    main()
