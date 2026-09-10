import argparse
import csv
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from .model import CONFIGS
from .run_task import METHODS, RESULT_SCHEMA_VERSION
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
        return (
            result.get("status") in {
                "OPTIMAL",
                "UNSAT",
                "TIMEOUT",
            }
            and result.get("timeout_scope") == "task"
            and result.get("result_schema_version") == RESULT_SCHEMA_VERSION
        )
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
            row["cpu_affinity"] = ",".join(
                map(str, row["cpu_affinity"])
            )

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
            writer = csv.DictWriter(
                f,
                fieldnames=fields,
            )
            writer.writeheader()
            for row in sorted(
                task_rows,
                key=lambda r: r.get("task_id", ""),
            ):
                writer.writerow(row)

        os.replace(tmp, out)

    if solve_rows:
        fields = sorted({k for row in solve_rows for k in row})
        tmp = run_dir / "solve_details.csv.tmp"
        out = run_dir / "solve_details.csv"

        with tmp.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=fields,
            )
            writer.writeheader()
            for row in solve_rows:
                writer.writerow(row)

        os.replace(tmp, out)


def kill_task_process(proc):
    if proc.poll() is not None:
        return

    try:
        if os.name == "posix":
            os.killpg(proc.pid, signal.SIGKILL)
        else:
            proc.kill()
    except ProcessLookupError:
        pass
    finally:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def read_progress(progress):
    if not progress.exists():
        return {}

    try:
        return json.loads(
            progress.read_text(encoding="utf-8")
        )
    except Exception:
        return {}


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
    p.add_argument(
        "--configs",
        nargs="+",
        default=["all"],
    )

    p.add_argument(
        "--task-timeout",
        "--solve-timeout",
        dest="task_timeout",
        type=float,
        default=3600,
        help=(
            "Hard wall-clock timeout for one complete task, including "
            "input/bounds, model construction, every solve() call, "
            "verification, and result writing. "
            "--solve-timeout is kept as a deprecated alias."
        ),
    )

    p.add_argument(
        "--cpu-core",
        type=int,
        default=1,
        help=(
            "Pin every SAT task to this single logical CPU. "
            "Use 0 on a 1-vCPU VM."
        ),
    )

    p.add_argument(
        "--settle-seconds",
        type=float,
        default=1.0,
        help=(
            "Fixed quiet delay between tasks; "
            "excluded from task timing."
        ),
    )

    args = p.parse_args()

    if args.task_timeout <= 0:
        raise SystemExit("--task-timeout must be > 0")

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
            f"--cpu-core={args.cpu_core} is invalid; "
            f"VM exposes {cpu_count} CPUs."
        )

    configs = parse_selection(
        args.configs,
        sorted(CONFIGS),
    )
    solvers = parse_selection(
        args.solvers,
        ["cadical300", "cryptominisat"],
    )
    methods = parse_selection(
        args.methods,
        METHODS,
    )

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
                    progress = (
                        result_dir
                        / f"{task_id}.progress.json"
                    )

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
        f"timeout_per_task={args.task_timeout}s | "
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
            "--task-timeout",
            str(args.task_timeout),
        ]

        out_path = log_dir / f"{task_id}.out.log"
        err_path = log_dir / f"{task_id}.err.log"

        print(f"[{index}/{total}] START {task_id}")

        task_started = time.monotonic()
        parent_timed_out = False

        with out_path.open(
            "w",
            encoding="utf-8",
        ) as stdout_handle, err_path.open(
            "w",
            encoding="utf-8",
        ) as stderr_handle:

            proc = subprocess.Popen(
                cmd,
                cwd=repo_root,
                stdout=stdout_handle,
                stderr=stderr_handle,
                env=child_env,
                start_new_session=True,
            )

            try:
                rc = proc.wait(
                    timeout=args.task_timeout
                )
            except subprocess.TimeoutExpired:
                parent_timed_out = True
                kill_task_process(proc)
                rc = TIMEOUT_EXIT_CODE

        observed_task_wall = (
            time.monotonic() - task_started
        )

        if rc == TIMEOUT_EXIT_CODE:
            progress_data = read_progress(progress)

            atomic_json(output, {
                "result_schema_version": RESULT_SCHEMA_VERSION,
                "task_id": task_id,
                "instance": str(instance),
                "config": config,
                "solver": solver,
                "method": method,
                **progress_data,
                "status": "TIMEOUT",
                "timeout_scope": "task",
                "task_timeout_s": args.task_timeout,
                "task_wall_time_s": round(
                    observed_task_wall,
                    9,
                ),
                "timeout_source": (
                    "batch_guard"
                    if parent_timed_out
                    else progress_data.get(
                        "timeout_source",
                        "task_watchdog",
                    )
                ),
                "timing_mode": "single_job",
                "cpu_core": args.cpu_core,
            })

            print(
                f"[{index}/{total}] TIMEOUT {task_id} "
                f"after {observed_task_wall:.3f}s "
                f"at bandwidth="
                f"{progress_data.get('bandwidth_check')}"
            )

        elif rc != 0 and not output.exists():
            atomic_json(output, {
                "result_schema_version": RESULT_SCHEMA_VERSION,
                "task_id": task_id,
                "instance": str(instance),
                "config": config,
                "solver": solver,
                "method": method,
                "status": "ERROR",
                "returncode": rc,
                "timeout_scope": "task",
                "task_timeout_s": args.task_timeout,
                "task_wall_time_s": round(
                    observed_task_wall,
                    9,
                ),
                "timing_mode": "single_job",
                "cpu_core": args.cpu_core,
            })

            print(
                f"[{index}/{total}] "
                f"ERROR rc={rc} {task_id}"
            )

        else:
            try:
                data = json.loads(
                    output.read_text(encoding="utf-8")
                )
                data["result_schema_version"] = (
                    RESULT_SCHEMA_VERSION
                )
                data["timeout_scope"] = "task"
                data["task_timeout_s"] = args.task_timeout
                data["timing_mode"] = "single_job"
                data["cpu_core"] = args.cpu_core
                atomic_json(output, data)
            except Exception:
                pass

            print(f"[{index}/{total}] DONE {task_id}")

        progress.unlink(missing_ok=True)
        write_tables(run_dir)

        if (
            args.settle_seconds > 0
            and index < total
        ):
            time.sleep(args.settle_seconds)

    write_tables(run_dir)


if __name__ == "__main__":
    main()
