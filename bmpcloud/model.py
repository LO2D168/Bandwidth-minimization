from dataclasses import dataclass
from pysat.formula import IDPool

from .cardinality import add_cardinality


@dataclass(frozen=True)
class ModelConfig:
    name: str
    representation: str
    mode: str
    encoding: str | None


CONFIGS = {
    "amo_seqcounter": ModelConfig(
        "amo_seqcounter", "transition", "at_most_one", "seqcounter"
    ),
    "amo_ladder": ModelConfig(
        "amo_ladder", "transition", "at_most_one", "ladder"
    ),
    "alo_direct": ModelConfig(
        "alo_direct", "transition", "at_least_one", None
    ),
    "eo_seqcounter": ModelConfig(
        "eo_seqcounter", "transition", "equal_one", "seqcounter"
    ),
    "eo_ladder": ModelConfig(
        "eo_ladder", "transition", "equal_one", "ladder"
    ),
    "ek_totalizer": ModelConfig(
        "ek_totalizer", "direct_l", "equal_k", "totalizer"
    ),
    "ek_cardnetwrk": ModelConfig(
        "ek_cardnetwrk", "direct_l", "equal_k", "cardnetwrk"
    ),
}


class ModelContext:
    def __init__(self, n):
        self.n = n
        self.base_vars = n * n
        self.vpool = IDPool(start_from=self.base_vars + 1)

    def L(self, row, col):
        return (row - 1) * self.n + col

    @property
    def top_var(self):
        return max(self.base_vars, self.vpool.top)


def build_static_model(n, adj, solver, config_name):
    cfg = CONFIGS[config_name]
    ctx = ModelContext(n)
    L = ctx.L
    num_clause = 0

    if cfg.representation == "direct_l":
        for col in range(1, n + 1):
            lits = [L(row, col) for row in range(1, n + 1)]
            num_clause += add_cardinality(
                solver=solver,
                lits=lits,
                mode="equal_k",
                vpool=ctx.vpool,
                encoding=cfg.encoding,
                k= n - col + 1,
            )

    elif cfg.representation == "transition":
        for col in range(2, n + 1):
            transitions = []

            for row in range(1, n + 1):
                t = ctx.vpool.id()
                solver.add_clause([-t, -L(row, col)])
                solver.add_clause([-t, L(row, col - 1)])
                solver.add_clause([L(row, col), -L(row, col - 1), t])
                num_clause += 3

                transitions.append(t)

            num_clause += add_cardinality(
                solver=solver,
                lits=transitions,
                mode=cfg.mode,
                vpool=ctx.vpool,
                encoding=cfg.encoding,
            )

        last_label = [
            L(row, n)
            for row in range(1, n + 1)
        ]

        num_clause += add_cardinality(
            solver=solver,
            lits=last_label,
            mode=cfg.mode,
            vpool=ctx.vpool,
            encoding=cfg.encoding,
        )

    else:
        raise ValueError(f"Unknown representation: {cfg.representation}")

    # Monotonic L.
    for row in range(1, n + 1):
        solver.add_clause([L(row, 1)])
        num_clause += 1

    for row in range(1, n + 1):
        for col in range(1, n):
            solver.add_clause([-L(row, col + 1), L(row, col)])
            num_clause += 1

    return ctx, num_clause


def bandwidth_clauses(n, adj, bandwidth, ctx):
    L = ctx.L

    for u in range(1, n + 1):
        for v in adj[u]:
            for label in range(1, n + 1):
                if label - bandwidth - 1 >= 0:
                    yield [
                        -L(u, label),
                        L(v, label - bandwidth),
                    ]


def add_bandwidth_bound(n, adj, bandwidth, ctx, solver):
    count = 0
    for clause in bandwidth_clauses(n, adj, bandwidth, ctx):
        solver.add_clause(clause)
        count += 1
    return count


def add_guarded_bandwidth_bound(
    n,
    adj,
    bandwidth,
    ctx,
    solver,
    selector,
):
    count = 0
    for clause in bandwidth_clauses(n, adj, bandwidth, ctx):
        solver.add_clause([-selector, *clause])
        count += 1
    return count
