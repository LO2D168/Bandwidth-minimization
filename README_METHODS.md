# BMP: 3 SAT solving strategies × 2 solvers

Kiến trúc cuối:

Task =
instance
× constraint configuration
× solver
× solving method

## 1. Repeated SAT

Mỗi bandwidth tạo solver mới:

UB:
  create solver
  build static CNF
  build bandwidth CNF
  solve
  delete

UB-1:
  create solver
  build lại từ đầu
  solve
  delete

Đây là baseline gần nhất với code cũ.

## 2. Incremental SAT

Một solver cho cả instance:

create solver
build static CNF một lần

for bandwidth from UB down:
    add clauses của bound mới
    solve cùng solver

Learned clauses và solver state được giữ lại.

## 3. Assumption SAT

Một solver cho cả instance.

Mỗi bandwidth b có selector a_b:

    (not a_b OR C_b)

Sau đó:

    solve(assumptions=[a_b])

Không rebuild solver và có thể reuse learnt clauses.
Nhược điểm là phải giữ guarded clauses của nhiều bound trong cùng solver.

## run_solver được tách theo phương pháp

bmpcloud/run_solver/
├── repeated.py
├── incremental.py
├── assumption.py
└── common.py

Solver backend độc lập:

bmpcloud/solver_backends.py

Do đó cùng một run_solver chạy được:
- CaDiCaL 3.0.0
- CryptoMiniSat

## Chạy riêng từng phương pháp

Repeated:

```bash
python -m bmpcloud.batch \
  --run-dir cloud_runs/repeated \
  --methods repeated \
  --configs eo_seqcounter ek_totalizer \
  --solvers cadical300 cryptominisat \
  --jobs 12
```

Incremental:

```bash
python -m bmpcloud.batch \
  --run-dir cloud_runs/incremental \
  --methods incremental \
  --configs eo_seqcounter ek_totalizer \
  --solvers cadical300 cryptominisat \
  --jobs 12
```

Assumption:

```bash
python -m bmpcloud.batch \
  --run-dir cloud_runs/assumption \
  --methods assumption \
  --configs eo_seqcounter ek_totalizer \
  --solvers cadical300 cryptominisat \
  --jobs 12
```

Tất cả:

```bash
python -m bmpcloud.batch \
  --run-dir cloud_runs/all \
  --methods repeated incremental assumption \
  --configs all \
  --solvers cadical300 cryptominisat \
  --jobs 12
```

## 3 VM

VM1:
```bash
SHARD_INDEX=0 JOBS=12 RUN_ID=paper01 ./scripts/run_3vm.sh
```

VM2:
```bash
SHARD_INDEX=1 JOBS=12 RUN_ID=paper01 ./scripts/run_3vm.sh
```

VM3:
```bash
SHARD_INDEX=2 JOBS=12 RUN_ID=paper01 ./scripts/run_3vm.sh
```

## Timeout

Không dùng Python thread để timeout solver.

Mỗi task là một OS process. Batch parent kill toàn process group khi quá timeout.
Cách này giữ được incremental state bên trong task nhưng vẫn có hard timeout ở
cấp toàn instance.

## Lưu ý về Assumption SAT

Assumption SAT và Incremental SAT đều reuse một solver, nhưng không giống nhau:

Incremental:
  formula chỉ mạnh dần do add clause.

Assumption:
  formula chứa các clause được guard bởi selector;
  mỗi solve call bật một selector qua assumptions.

Do đó cần benchmark riêng cả ba phương pháp.
