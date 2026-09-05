# Experiment dimensions

Task = instance × constraint_config × solver × solving_method

## Solvers
- cadical300       = CaDiCaL 3.0.0 through PySAT Cadical300
- cryptominisat    = CryptoMiniSat through PySAT CryptoMinisat

## Solving methods
- repeated
- incremental
- assumption

## Constraint configs
- amo_seqcounter
- amo_ladder
- alo_direct
- eo_seqcounter
- eo_ladder
- ek_totalizer
- ek_cardnetwrk

Full matrix for 1 graph:
7 configs × 2 solvers × 3 methods = 42 tasks.
