from .common import new_search_state, finalize_search
from ..model import build_static_model, add_bandwidth_bound
from ..solver_backends import make_solver
from ..solve_timeout import write_task_progress
from ..timing import now, elapsed_seconds


def solve_repeated_sat(
    n, adj, lb, ub, solver_name, config_name,
    task_timeout_s=3600, task_started_monotonic=None, progress_path=None,
):
    """
    Repeated SAT:
      - one fresh solver per bandwidth;
      - rebuild the full formula for every check;
      - no solver state is reused between bandwidth values;
      - one wall-clock timeout covers the entire task.
    """
    state = new_search_state()

    for val in range(ub, lb - 1, -1):
        write_task_progress(
            progress_path,
            task_started_monotonic,
            task_timeout_s,
            status="BUILDING",
            method="repeated",
            solver=solver_name,
            config=config_name,
            bandwidth_check=val,
            check_index=state["checks"] + 1,
            best_sat=state["best_sat"],
            completed_solve_wall_time_s=round(
                state["solve_wall_time_s"], 9
            ),
            completed_build_wall_time_s=round(
                state["build_wall_time_s"], 9
            ),
        )

        build_wall0, build_cpu0 = now()

        solver = make_solver(solver_name)
        state["solver_builds"] += 1

        try:
            ctx, static_count = build_static_model(
                n,
                adj,
                solver,
                config_name,
            )
            bw_count = add_bandwidth_bound(
                n,
                adj,
                val,
                ctx,
                solver,
            )

            build_wall, build_cpu = elapsed_seconds(
                build_wall0,
                build_cpu0,
            )
            state["build_wall_time_s"] += build_wall
            state["build_cpu_time_s"] += build_cpu

            state["checks"] += 1
            state["solve_calls"] += 1
            state["static_clauses"] += static_count
            state["bandwidth_clauses"] += bw_count
            state["max_var"] = max(
                state["max_var"],
                ctx.top_var,
            )

            write_task_progress(
                progress_path,
                task_started_monotonic,
                task_timeout_s,
                status="SOLVING",
                method="repeated",
                solver=solver_name,
                config=config_name,
                bandwidth_check=val,
                check_index=state["checks"],
                best_sat=state["best_sat"],
                completed_solve_wall_time_s=round(
                    state["solve_wall_time_s"], 9
                ),
                completed_build_wall_time_s=round(
                    state["build_wall_time_s"], 9
                ),
            )

            solve_wall0, solve_cpu0 = now()
            sat = solver.solve()
            solve_wall, solve_cpu = elapsed_seconds(
                solve_wall0,
                solve_cpu0,
            )

            state["solve_wall_time_s"] += solve_wall
            state["solve_cpu_time_s"] += solve_cpu

            state["solve_records"].append({
                "check_index": state["checks"],
                "bandwidth": val,
                "sat": bool(sat),
                "build_wall_time_s": round(build_wall, 9),
                "build_cpu_time_s": round(build_cpu, 9),
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

    state["build_wall_time_s"] = round(
        state["build_wall_time_s"], 9
    )
    state["build_cpu_time_s"] = round(
        state["build_cpu_time_s"], 9
    )
    state["solve_wall_time_s"] = round(
        state["solve_wall_time_s"], 9
    )
    state["solve_cpu_time_s"] = round(
        state["solve_cpu_time_s"], 9
    )

    status, optimum, model = finalize_search(state, lb)
    return status, optimum, model, state
