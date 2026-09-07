from .common import new_search_state, finalize_search
from ..model import build_static_model, add_guarded_bandwidth_bound
from ..solver_backends import make_solver
from ..solve_timeout import solve_with_hard_timeout
from ..timing import now, elapsed_seconds


def solve_assumption_sat(
    n, adj, lb, ub, solver_name, config_name,
    solve_timeout_s=3000, progress_path=None,
):
    """
    Assumption SAT:
      - exactly one solver for the entire task;
      - every candidate bandwidth has a selector variable;
      - guarded bandwidth clauses are built once;
      - each check uses solve(assumptions=[selector]).
    """
    state = new_search_state()

    build_wall0, build_cpu0 = now()
    solver = make_solver(solver_name)
    state["solver_builds"] = 1

    try:
        ctx, static_count = build_static_model(n, adj, solver, config_name)
        state["static_clauses"] = static_count

        selectors = {}

        for val in range(ub, lb - 1, -1):
            selector = ctx.vpool.id()
            selectors[val] = selector

            state["bandwidth_clauses"] += add_guarded_bandwidth_bound(
                n=n,
                adj=adj,
                bandwidth=val,
                ctx=ctx,
                solver=solver,
                selector=selector,
            )

        state["max_var"] = ctx.top_var

        build_wall, build_cpu = elapsed_seconds(build_wall0, build_cpu0)
        state["build_wall_time_s"] = build_wall
        state["build_cpu_time_s"] = build_cpu

        for val in range(ub, lb - 1, -1):
            state["checks"] += 1
            state["solve_calls"] += 1

            solve_wall0, solve_cpu0 = now()

            sat = solve_with_hard_timeout(
                solver,
                timeout_s=solve_timeout_s,
                assumptions=[selectors[val]],
                progress_path=progress_path,
                metadata={
                    "method": "assumption",
                    "solver": solver_name,
                    "config": config_name,
                    "bandwidth_check": val,
                    "check_index": state["checks"],
                    "selector": selectors[val],
                    "completed_solve_wall_time_s": round(state["solve_wall_time_s"], 9),
                    "completed_build_wall_time_s": round(state["build_wall_time_s"], 9),
                },
            )

            solve_wall, solve_cpu = elapsed_seconds(solve_wall0, solve_cpu0)
            state["solve_wall_time_s"] += solve_wall
            state["solve_cpu_time_s"] += solve_cpu

            state["solve_records"].append({
                "check_index": state["checks"],
                "bandwidth": val,
                "sat": bool(sat),
                # All guarded bounds are prebuilt, so per-check build is zero.
                "build_wall_time_s": 0.0,
                "build_cpu_time_s": 0.0,
                "solve_wall_time_s": round(solve_wall, 9),
                "solve_cpu_time_s": round(solve_cpu, 9),
            })

            if sat is True:
                state["best_sat"] = val
                state["last_model"] = solver.get_model()

            elif sat is False:
                break

            else:
                raise RuntimeError(
                    f"Unexpected solver result at bandwidth {val}: {sat}"
                )

    finally:
        solver.close()

    state["build_wall_time_s"] = round(state["build_wall_time_s"], 9)
    state["build_cpu_time_s"] = round(state["build_cpu_time_s"], 9)
    state["solve_wall_time_s"] = round(state["solve_wall_time_s"], 9)
    state["solve_cpu_time_s"] = round(state["solve_cpu_time_s"], 9)

    status, optimum, model = finalize_search(state, lb)
    return status, optimum, model, state
