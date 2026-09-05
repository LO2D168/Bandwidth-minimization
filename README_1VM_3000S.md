# 1 VM + timeout 3000s per solve call

`3000s` applies to each individual SAT call, not to the whole graph.

Example:

- solve(B=20) = 1200s -> continue
- solve(B=19) = 2400s -> continue
- solve(B=18) reaches 3000s -> this task becomes TIMEOUT

For incremental/assumption solving, successful calls reuse the same solver object.
If one call reaches 3000s, the task process is terminated because the exact optimum
can no longer be established beyond that unresolved bandwidth.

Run:

```bash
chmod +x scripts/run_1vm.sh
JOBS=8 SOLVE_TIMEOUT=3000 RUN_ID=paper01 ./scripts/run_1vm.sh
```

Selected configs/methods:

```bash
python -m bmpcloud.batch \
  --run-dir cloud_runs/test \
  --configs eo_seqcounter eo_ladder ek_totalizer ek_cardnetwrk \
  --methods repeated incremental assumption \
  --solvers cadical300 cryptominisat \
  --jobs 8 \
  --solve-timeout 3000
```
