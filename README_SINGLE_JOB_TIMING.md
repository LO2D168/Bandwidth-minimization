# Final timing mode: 1 VM, exactly 1 active SAT task

This version is intentionally optimized for measurement quality, not throughput.

## Invariants

- Exactly one experiment task runs at a time.
- Each task is pinned to one logical CPU with `taskset`.
- No `--jobs` option exists in the timing scheduler.
- Each solver.solve() call has a 3000 s wall-clock timeout.
- A fixed deterministic task shuffle (`seed=2026`) reduces ordering bias.
- Common numerical-library thread counts are forced to 1.
- A fixed 1 s idle interval is inserted between completed tasks by default.
- Timing uses `time.perf_counter_ns()` for wall time and `time.process_time_ns()`
  for process CPU time.

## Timing fields

Each task JSON records:

- task_wall_time_s
- task_cpu_time_s
- build_wall_time_s
- build_cpu_time_s
- solve_wall_time_s
- solve_cpu_time_s
- cpu_affinity
- solve_records[] with one row per bandwidth check

Two CSV files are produced:

- `summary.csv`: one row per task
- `solve_details.csv`: one row per individual solver.solve() call

## Run

On a VM with more than one vCPU:

```bash
chmod +x scripts/run_1vm.sh
CPU_CORE=1 SOLVE_TIMEOUT=3000 RUN_ID=paper01_timing ./scripts/run_1vm.sh
```

On a 1-vCPU VM use:

```bash
CPU_CORE=0 SOLVE_TIMEOUT=3000 RUN_ID=paper01_timing ./scripts/run_1vm.sh
```

## Interpretation

For solver comparison, `solve_wall_time_s` is the primary SAT-solving metric.

For end-to-end formulation comparison, use `task_wall_time_s`.

For diagnosing external waiting / scheduling effects compare wall time against CPU time.
