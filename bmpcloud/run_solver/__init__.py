from .repeated import solve_repeated_sat
from .incremental import solve_incremental_sat
from .assumption import solve_assumption_sat

RUNNERS = {
    "repeated": solve_repeated_sat,
    "incremental": solve_incremental_sat,
    "assumption": solve_assumption_sat,
}
