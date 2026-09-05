from pysat.solvers import Cadical300, CryptoMinisat


class SolverBackend:
    def add_clause(self, clause):
        raise NotImplementedError

    def solve(self, assumptions=None):
        raise NotImplementedError

    def get_model(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError


class Cadical300Backend(SolverBackend):

    def __init__(self):
        self.solver = Cadical300()

    def add_clause(self, clause):
        self.solver.add_clause(clause)

    def solve(self, assumptions=None):
        return self.solver.solve(assumptions=assumptions or [])

    def get_model(self):
        return self.solver.get_model()

    def close(self):
        self.solver.delete()


class CryptoMiniSatBackend(SolverBackend):

    def __init__(self):
        self.solver = CryptoMinisat()

    def add_clause(self, clause):
        self.solver.add_clause(clause)

    def solve(self, assumptions=None):
        return self.solver.solve(assumptions=assumptions or [])

    def get_model(self):
        return self.solver.get_model()

    def close(self):
        self.solver.delete()


def make_solver(name):
    name = name.lower()

    if name in {"cadical", "cadical300"}:
        return Cadical300Backend()

    if name in {"cms", "cryptominisat"}:
        return CryptoMiniSatBackend()

    raise ValueError(f"Unsupported solver: {name}")
