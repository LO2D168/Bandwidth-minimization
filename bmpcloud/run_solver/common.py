def new_search_state():
    return {
        "best_sat": None,
        "last_model": None,

        "checks": 0,
        "solver_builds": 0,
        "solve_calls": 0,

        "static_clauses": 0,
        "bandwidth_clauses": 0,
        "max_var": 0,

        # High-level timing totals.
        "build_wall_time_s": 0.0,
        "build_cpu_time_s": 0.0,
        "solve_wall_time_s": 0.0,
        "solve_cpu_time_s": 0.0,

        # Per solver.solve() timing details.
        "solve_records": [],
    }


def finalize_search(state, lb):
    if state["best_sat"] is not None:
        return "OPTIMAL", state["best_sat"], state["last_model"]

    return "UNSAT", -1, None
