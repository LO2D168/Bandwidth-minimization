from .common import new_search_state, finalize_search
from ..model import build_static_model, add_bandwidth_bound
from ..solver_backends import make_solver
from ..solve_timeout import solve_with_hard_timeout
from ..timing import now, elapsed_seconds


def solve_incremental_sat(
    n, adj, lb, ub, solver_name, config_name,
    solve_timeout_s=3000, progress_path=None,
):
    """
    Incremental SAT:
      - exactly one solver for the entire task;
      - static formula is built once;
      - stronger bandwidth constraints are appended;
      - learnt clauses / solver state are reused.
    """
    state = new_search_state()

    static_wall0, static_cpu0 = now()
    solver = make_solver(solver_name)
    state["solver_builds"] = 1

    try:
        ctx, static_count = build_static_model(n, adj, solver, config_name)

        static_wall, static_cpu = elapsed_seconds(static_wall0, static_cpu0)
        state["build_wall_time_s"] += static_wall
        state["build_cpu_time_s"] += static_cpu

        state["static_clauses"] = static_count
        state["max_var"] = ctx.top_var

        for val in range(ub, lb - 1, -1):
            bound_wall0, bound_cpu0 = now()

            bw_count = add_bandwidth_bound(n, adj, val, ctx, solver)

            bound_wall, bound_cpu = elapsed_seconds(bound_wall0, bound_cpu0)
            state["build_wall_time_s"] += bound_wall
            state["build_cpu_time_s"] += bound_cpu

            state["bandwidth_clauses"] += bw_count
            state["checks"] += 1
            state["solve_calls"] += 1

            solve_wall0, solve_cpu0 = now()

            sat = solve_with_hard_timeout(
                solver,
                timeout_s=solve_timeout_s,
                progress_path=progress_path,
                metadata={
                    "method": "incremental",
                    "solver": solver_name,
                    "config": config_name,
                    "bandwidth_check": val,
                    "check_index": state["checks"],
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
                "build_wall_time_s": round(bound_wall, 9),
                "build_cpu_time_s": round(bound_cpu, 9),
                "solve_wall_time_s": round(solve_wall, 9),
                "solve_cpu_time_s": round(solve_cpu, 9),
            })

            if sat:
                state["best_sat"] = val
                state["last_model"] = solver.get_model()
            else:
                break

    finally:
        solver.close()

    state["build_wall_time_s"] = round(state["build_wall_time_s"], 9)
    state["build_cpu_time_s"] = round(state["build_cpu_time_s"], 9)
    state["solve_wall_time_s"] = round(state["solve_wall_time_s"], 9)
    state["solve_cpu_time_s"] = round(state["solve_cpu_time_s"], 9)

    status, optimum, model = finalize_search(state, lb)
    return status, optimum, model, state
