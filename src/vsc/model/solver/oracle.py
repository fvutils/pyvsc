"""The dv-solve oracle check, from pyvsc: every answer dv-solve gives is
checked by a reference SMT solver (z3).

    vsc.set_solver_oracle(out_dir="oracle/%t-%p", tag="regress")
    ... randomize ...
    vsc.set_solver_oracle(False)          # finalises the run directory

Two questions per answer: does dv-solve's sat/unsat verdict agree with z3, and
do the values dv-solve produced satisfy the constraints, as z3 judges them.
Summarise one or many runs with ``python -m dv_solve.oracle report oracle/``.

What it checks is the problem pyvsc handed dv-solve, so it covers dv-solve
(its engines and its own SV elaboration), not pyvsc's translation of the model
-- VSC_DVSOLVE_XCHECK (xcheck.py, against Boolector) covers that layer. The
BV-SAT path (bvsat_sampler, dv_solve.bvsat) is not checked.

See packages/dv-solve/docs/api_oracle_plan.md.
"""


def set_solver_oracle(enable=True, **kwargs):
    """Check every dv-solve context pyvsc creates from now on.

    Args:
        enable: ``False``/``None`` stops checking and closes the current
            oracle (finalising its run directory). An existing
            ``dv_solve.oracle.Oracle`` is installed as is.
        **kwargs: Passed to ``dv_solve.oracle.Oracle``: ``solver`` ("z3" or
            "bitwuzla"), ``bin``, ``command``, ``out_dir`` (``%t`` time,
            ``%p`` pid), ``tag``, ``timeout_s``, ``keep_all``, and
            ``raise_on_fail`` (raise ``OracleMismatch`` from the randomize()
            whose answer was wrong).

    Returns:
        The installed ``Oracle``, or ``None``.
    """
    from dv_solve.oracle import Oracle, get_default_oracle, set_default_oracle
    prev = get_default_oracle()
    if not enable:
        set_default_oracle(None)
        if prev is not None:
            prev.close()
        return None
    o = enable if isinstance(enable, Oracle) else Oracle(**kwargs)
    set_default_oracle(o)
    if prev is not None and prev is not o:
        prev.close()
    return o


def get_solver_oracle():
    """The oracle checking dv-solve's answers, or ``None``."""
    try:
        from dv_solve.oracle import get_default_oracle
    except ImportError:
        return None
    return get_default_oracle()
