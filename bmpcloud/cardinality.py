from pysat.card import CardEnc, EncType


ENCODINGS = {
    "seqcounter": EncType.seqcounter,
    "ladder": EncType.ladder,
    "totalizer": EncType.totalizer,
    "cardnetwrk": EncType.cardnetwrk,
}


def add_cardinality(solver, lits, mode, vpool, encoding=None, k=None):
    if mode == "at_least_one":
        solver.add_clause(list(lits))
        return 1

    if encoding not in ENCODINGS:
        raise ValueError(f"Unsupported encoding: {encoding}")

    enc_type = ENCODINGS[encoding]

    if mode == "at_most_one":
        enc = CardEnc.atmost(
            lits=list(lits),
            bound=1,
            vpool=vpool,
            encoding=enc_type,
        )
    elif mode == "equal_one":
        enc = CardEnc.equals(
            lits=list(lits),
            bound=1,
            vpool=vpool,
            encoding=enc_type,
        )
    elif mode == "equal_k":
        if k is None:
            raise ValueError("equal_k requires k")
        enc = CardEnc.equals(
            lits=list(lits),
            bound=int(k),
            vpool=vpool,
            encoding=enc_type,
        )
    else:
        raise ValueError(f"Unknown cardinality mode: {mode}")

    for clause in enc.clauses:
        solver.add_clause(clause)

    return len(enc.clauses)
