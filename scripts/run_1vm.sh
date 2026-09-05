#!/usr/bin/env bash
set -euo pipefail

SOLVE_TIMEOUT="${SOLVE_TIMEOUT:-3000}"
RUN_ID="${RUN_ID:-paper01_timing}"
CPU_CORE="${CPU_CORE:-1}"
SCHEDULE_SEED="${SCHEDULE_SEED:-2026}"
SETTLE_SECONDS="${SETTLE_SECONDS:-1}"

python -m bmpcloud.batch \
  --repo-root . \
  --testcase-dir testcase \
  --run-dir "cloud_runs/${RUN_ID}" \
  --configs all \
  --solvers cadical300 cryptominisat \
  --methods repeated incremental assumption \
  --solve-timeout "${SOLVE_TIMEOUT}" \
  --cpu-core "${CPU_CORE}" \
  --settle-seconds "${SETTLE_SECONDS}"
