"""Near-uniform witness sampling for the dv-solve BV-SAT engine.

The BV-SAT engine (``BVSatCtx`` / kissat) is *complete* — authoritative for
SAT/UNSAT — but it returns *a* model, not a well-distributed one. Its raw model
stream is badly clustered (a ``uint64 inside [0..19]`` left three values
unreachable over 400 draws), so it is unusable as constrained-random *stimulus*.

This module makes the BV-SAT engine usable for SAT *serving* via the textbook
**XOR / parity-hashing** uniform-witness sampler (the family behind
ApproxMC / UniGen / CMSGen):

  * A random parity (XOR) constraint over a subset of the *sampling bits* —
    ``(b_i1 XOR b_i2 XOR ...) == r`` with each bit included with prob 1/2 and
    ``r`` a random bit — partitions the assignment space into two random halves.
  * Adding ``m`` independent random parities carves the space into ``~2^m``
    random "cells"; the solutions surviving in one cell are a near-uniform
    random subset of all solutions.
  * Choosing ``m ~ log2(#solutions)`` leaves ~1 solution per non-empty cell, so
    the single model the SAT solver returns from that cell is a near-uniform
    draw from the whole feasible set.

We don't know ``#solutions``, so we use a pragmatic incremental schedule (plan
§2.2(b)): build the base, then **add parity planes one at a time**, solving after
each, and stop at the first empty cell (UNSAT) — keeping the model from the last
satisfiable level. Because the planes are *nested* (each adds a constraint), the
last SAT level has the smallest non-empty cell, landing near ``log2(#solutions)``
— the uniform sweet spot. The base (zero planes) is known SAT here, so a valid
model is always available.

This incremental shape matters for performance: ``builder_finalize`` is
*non-destructive and additive*, so we build the base **once** and only append
planes to the same builder — no per-attempt re-translation/re-bit-blast of the
base (plan §2.8's rebuild-cost risk). The number of SAT solves is just
``critical_m + 1 ≈ log2(#solutions) + 1``. (BV-SAT is non-incremental, so each
level still needs a fresh ``BVSatCtx`` solve — but only finalize, a memcpy, is
repeated, not the translation.) The ``make_base`` factory is invoked exactly once
per ``sample`` call.

The XOR planes are built entirely from primitives the builder already exposes
(``expr_extract`` + ``BIN_BXOR`` + ``BIN_EQ``), so no new C is needed.

Determinism: the plane coefficients and the per-level kissat seed are derived
deterministically from the caller's ``seed``, so the same pyvsc seed reproduces
the same value stream (per-seed determinism; cross-version is not promised, like
any sampler change).

**Native sampling (v2 plan V19).** The schedule above now runs in the engine
(``dvs_bbsolver_sample``): the problem is bit-blasted once on an incremental
SAT backend (CaDiCaL), each plane is an assumption literal, and the level is
found top-first (one solve when the feasible set is too big to empty, else a
binary search), with the free bits diversified once, on the final model. A
65536-bit ``a < b`` draw went from ~1.2 s to ~25 ms. The Python loop below is
kept for a dv-solve built without CaDiCaL, and as an A/B reference
(``_NATIVE = False``).
"""
from __future__ import annotations

import random

_U64 = (1 << 64) - 1

# Cap the plane count. A feasible set above 2^_M_CAP cannot be covered by the
# handful of draws a randomize loop makes, so more planes only cost solves.
_M_CAP = 16

# Draw through the engine's sampler (dvs_bbsolver_sample) when the build has an
# incremental SAT backend. False forces the Python level loop (A/B).
_NATIVE = True

# Cap the bits hashed per variable. Critical for performance: kissat is plain
# CDCL and is *pathologically slow* on XOR/parity constraints (the CDCL worst
# case — CryptoMiniSat-style Gaussian elimination is what makes them cheap, and
# kissat has none). A parity over a 64-bit free variable's full width produces a
# 64-long XOR chain that kissat chokes on. Hashing only the low bits keeps the
# chains short. Domains up to 2^this get every bit hashed (full coverage where it
# matters); wider domains get their low bits hashed — enough to de-cluster, and
# their full range is uncoverable by a sampling loop anyway.
_MAX_HASH_BITS_PER_VAR = 16


def _effective_bits(vid, width, lo, hi, is_signed):
    """The variable bit positions a parity may sample.

    Any subset of bits gives a *valid* random hash (a parity only partitions the
    solution set; it never drops a solution improperly), so we are free to pick
    the bits that actually vary. For an unsigned field anchored at 0 the value is
    carried by its low ``ceil(log2(hi+1))`` bits, so hashing only those makes
    each plane far more balanced on a 64-bit-wide-but-small-range var (the canary
    case). For signed / offset domains the bit→value mapping is not low-bit-local
    (two's complement), so we conservatively use the full width."""
    if not is_signed and lo == 0 and hi >= 0:
        eff = max(1, hi.bit_length())
        eff = min(eff, width)
    else:
        eff = width
    # Bound the XOR-chain length (kissat is slow on long parities — see
    # _MAX_HASH_BITS_PER_VAR). Hashing the low bits de-clusters; the high bits of
    # a very wide domain are uncoverable by a sampling loop regardless.
    eff = min(eff, _MAX_HASH_BITS_PER_VAR)
    return [(vid, i) for i in range(eff)]


def _sampling_bits(sample_vars):
    bits = []
    for (vid, width, lo, hi, is_signed) in sample_vars:
        bits.extend(_effective_bits(vid, width, lo, hi, is_signed))
    return bits


def _estimate_n(sample_vars):
    """Upper-bound the feasible-set size from the declared domains (ignores
    relational constraints, which only shrink it — handled by the retry)."""
    n = 1
    for (vid, width, lo, hi, is_signed) in sample_vars:
        span = hi - lo + 1
        if span < 1:
            span = 1
        n *= span
        if n >= (1 << (_M_CAP + 2)):
            return 1 << (_M_CAP + 2)
    return n


def _estimate_m(sample_vars, n_bits):
    """Target plane count ≈ floor(log2(n_est)), capped by the bit budget and
    ``_M_CAP``. Cells then hold ~1 solution."""
    n = _estimate_n(sample_vars)
    if n <= 1:
        return 0
    m = n.bit_length() - 1          # floor(log2(n)) for n a power of two; >= it otherwise
    return max(0, min(m, n_bits, _M_CAP))


def _append_one_plane(b, bits, rng):
    """Append a single random parity constraint over ``bits`` to the builder.
    Each bit joins with probability 1/2; an empty selection is re-drawn (a
    degenerate ``0 == r`` plane would waste a level). Returns ``True`` if a plane
    was added."""
    from dv_solve.problem import BIN_BXOR, BIN_EQ
    for _ in range(8):  # re-draw a few times if the random subset came up empty
        terms = [b.expr_extract(b.expr_var(vid), bit, bit)
                 for (vid, bit) in bits if rng.getrandbits(1)]
        if terms:
            # Balanced XOR tree (depth log2(n)): a left-deep chain over a large
            # RandSet exceeds BV-SAT's expression-depth limit.
            while len(terms) > 1:
                nxt = [b.expr_binary(BIN_BXOR, terms[i], terms[i + 1])
                       for i in range(0, len(terms) - 1, 2)]
                if len(terms) % 2:
                    nxt.append(terms[-1])
                terms = nxt
            r = rng.getrandbits(1)
            b.add_constraint(b.expr_binary(BIN_EQ, terms[0], b.expr_const(r)))
            return True
    return False


def _read_model(bb, vid, ws_by_vid):
    """Variable ``vid``'s value in ``bb``'s model, as its field reads it."""
    ws = ws_by_vid.get(vid)
    if ws is None:
        return bb.value(vid)
    width, signed = ws
    if width > 64:
        return bb.value_wide(vid, width, signed)
    # int64 fast path: reinterpret as unsigned for an unsigned field whose
    # top bit is set (only at width 64), matching the field's declared sign.
    v = bb.value(vid)
    return v if signed else v & ((1 << width) - 1)


def open_native(problem_buf):
    """An incremental BV-SAT context over the finalized ``problem_buf`` for
    :func:`draw_native`, or ``None`` when ``_NATIVE`` is off or the build has
    no incremental SAT backend. The caller destroys it."""
    if not _NATIVE:
        return None
    from dv_solve.bvsat import BVSatCtx
    bb = BVSatCtx(problem_buf, incremental=True)
    if not bb.is_incremental():
        bb.destroy()
        return None
    return bb


def draw_native(bb, readback, sample_vars, seed, solve_info=None, soft_keep=None):
    """Draw a near-uniform model with the engine's sampler
    (``dvs_bbsolver_sample``) on ``bb`` (from :func:`open_native`) and, on SAT,
    write it into the readback fields. The first draw encodes the problem;
    later draws on the same ``bb`` only solve. Returns the BV-SAT verdict, which
    is authoritative (a complete engine): ``BVSAT_SAT``, ``BVSAT_UNSAT`` (no
    model at all), or UNKNOWN / ERROR."""
    from dv_solve.bvsat import BVSAT_SAT
    if solve_info is not None:
        solve_info.n_sat_calls += 1
    rc = bb.sample([sv[0] for sv in sample_vars], seed, soft_keep=soft_keep)
    if rc == BVSAT_SAT:
        ws = {vid: (width, signed) for (vid, width, _lo, _hi, signed) in sample_vars}
        for f, vid in readback:
            f.set_val(_read_model(bb, vid, ws))
    return rc


def sample_problem(problem_buf, readback, sample_vars, seed,
                   solve_info=None, soft_keep=None):
    """One :func:`draw_native` on a fresh context over ``problem_buf``.
    Returns its verdict, or ``None``, having done nothing, when there is no
    native sampler (see :func:`open_native`)."""
    bb = open_native(problem_buf)
    if bb is None:
        return None
    try:
        return draw_native(bb, readback, sample_vars, seed,
                           solve_info=solve_info, soft_keep=soft_keep)
    finally:
        bb.destroy()


def sample(make_base, readback, sample_vars, seed,
           solve_info=None, m_max=None, soft_keep=None):
    """Draw a near-uniform model and write it into the readback fields.

    ``make_base``  — zero-arg factory returning a fresh, finalize-ready
                     ``SolveProblemBuilder`` for the base problem (same vars/ids
                     as ``readback``). Invoked once (twice on a dv-solve
                     without CaDiCaL, which takes the Python loop).
    ``readback``   — list of ``(field, var_id)`` to write the model into.
    ``sample_vars``— list of ``(var_id, width, lo, hi, is_signed)`` describing
                     the declared domain of each rand field (for bit selection
                     and the plane-count ceiling).
    ``seed``       — per-call seed; same seed → same value stream.
    ``solve_info`` — optional telemetry object; ``n_sat_calls`` is incremented
                     once per BV-SAT solve.
    ``m_max``      — optional ceiling on the number of planes (defaults to the
                     domain-derived estimate plus a small margin).

    Returns ``True`` on success (fields written) or ``None`` if no model was
    found at any level (caller should fall back — should not happen, since the
    base level is known SAT).
    """
    from dv_solve.bvsat import BVSatCtx, BVSAT_SAT

    # Per-var (width, signed) for readback: >64-bit vars need the limb-based
    # reader (value_wide); <=64-bit use the int64 fast path.
    _ws = {vid: (width, signed)
           for (vid, width, _lo, _hi, signed) in sample_vars}

    if _NATIVE and m_max is None:
        b = make_base()
        try:
            buf, _sz = b.finalize()
        finally:
            b.destroy()
        rc = sample_problem(buf, readback, sample_vars, seed,
                            solve_info=solve_info, soft_keep=soft_keep)
        if rc is not None:
            return True if rc == BVSAT_SAT else None
        # No incremental backend in this build: the Python loop, below.

    def _read(bb, vid):
        ws = _ws.get(vid)
        if ws is None:
            return bb.value(vid)
        return _read_model(bb, vid, _ws)

    bits = _sampling_bits(sample_vars)
    if m_max is None:
        # The estimate over-bounds log2(#solutions) (it ignores constraints),
        # and the critical level is at most that — a small margin covers the
        # estimate being slightly low for a near-power-of-two feasible set.
        m_max = min(len(bits), _estimate_m(sample_vars, len(bits)) + 2, _M_CAP)

    rng = random.Random(seed & _U64)
    b = make_base()
    best = None
    try:
        k = 0
        while True:
            buf, _sz = b.finalize()           # cheap snapshot (memcpy), additive
            bb = BVSatCtx(buf)
            try:
                if solve_info is not None:
                    solve_info.n_sat_calls += 1
                rc = bb.check(seed=rng.randint(0, (1 << 63) - 1),
                              soft_keep=soft_keep)
                if rc == BVSAT_SAT:
                    # Nested cells: each level is a subset of the previous, so the
                    # highest SAT level has the tightest (most uniform) cell.
                    best = [(f, _read(bb, vid)) for (f, vid) in readback]
                else:
                    break  # this plane emptied the cell — use the last SAT model
            finally:
                bb.destroy()
            if k >= m_max or not bits:
                break
            if not _append_one_plane(b, bits, rng):
                break
            k += 1
    finally:
        b.destroy()

    if best is None:
        return None
    for f, val in best:
        f.set_val(val)
    return True


# --------------------------------------------------------------------------- #
# Staged (solve-order-honoring) sampling                                        #
# --------------------------------------------------------------------------- #
# A plain uniform sample draws from the *joint* feasible set and so has no notion
# of `solve_order` — and the joint distribution is the WRONG one. `solve_order(a,
# c)` means "pick a value for `a` from its own domain first, commit, then solve
# the rest", NOT "uniform over {(a,c)}". The distinction is the whole point of the
# canary `test_before_and_after_lists`: with `c==0 -> a==0`, a joint-uniform draw
# sets `a==0` whenever `c==0` (~half the draws), but solving `a` first picks a
# (almost surely non-zero) value and *forces* `c!=0` — so `a>0` on every draw.
#
# The Boolector swizzler gets this by, per order stage, ASSUMING a random value
# from each field's domain, checking SAT, and ASSERTING it (retrying on UNSAT) —
# `solvegroup_swizzler_partsel.swizzle_field`. `sample_ordered` mirrors that: each
# non-final stage pins its fields to random domain targets (validated SAT against
# the prior pins + the still-free later stages), and the final/unordered stage is
# served by the ordinary uniform `sample` with the earlier stages pinned. This
# reproduces the per-stage "choose from own domain, then constrain downstream"
# marginal, not the joint.

_INT64_MIN = -(1 << 63)
_INT64_MAX = (1 << 63) - 1


def _pack_const64(v, width, signed):
    """Pack a chosen field value into the int64 carrier ``expr_const`` takes,
    mirroring ``dvsolve_translator.visit_expr_literal``: a value that fits a
    signed int64 goes in directly; a ``<=64``-bit pattern that overflows signed
    int64 (a uint64 ``>= 2^63``) goes in as its two's-complement reinterpretation
    (the same bit pattern). Width is ``<=64`` here (``_pin_eq`` takes wider
    values as a wide constant).

    ``expr_const`` is unsized, so the carrier must hold the field's *value*, not
    its bit pattern at ``width``: a signed field keeps its sign (masking -7 on an
    int32 to ``2^32-7`` would make ``var == const`` unsatisfiable)."""
    v &= (1 << width) - 1                       # bit pattern at width
    if signed and v >= (1 << (width - 1)):
        v -= (1 << width)                       # sign-extend: value, not pattern
    if v > _INT64_MAX:
        v -= (1 << 64)
    return v


def _pin_eq(b, vid, v, width, signed):
    """``var == v`` for a chosen value ``v`` of a field of ``width`` bits. A
    ``<=64``-bit value goes in the int64 carrier (``_pack_const64``); a wider
    one is a single wide-constant node at the field's own width and sign."""
    from dv_solve.problem import BIN_EQ
    if width > 64:
        k = b.expr_const_wide(v, width, is_signed=signed)
    else:
        k = b.expr_const(_pack_const64(v, width, signed), signed)
    return b.expr_binary(BIN_EQ, b.expr_var(vid), k)


# Per-stage attempts at a random domain target before giving up and serving that
# stage with a constrained uniform sample (mirrors the swizzler's bounded retry).
_STAGE_PIN_ATTEMPTS = 8


def sample_ordered(make_base, order_stages, sample_vars, seed, solve_info=None,
                   soft_keep=None):
    """Staged sampling that honors ``solve_order`` (see the section comment).

    ``make_base``    — the same zero-arg base-problem factory ``sample`` takes.
    ``order_stages`` — list of stages, each a list of ``(field, var_id)``, in
                       solve order (earliest-solved first); the last stage may be
                       the unordered remainder. Every rand field appears once.
    ``sample_vars``  — full ``[(vid,width,lo,hi,is_signed)]`` for all rand fields.
    ``seed``         — per-call seed; same seed → same value stream.

    Each *non-final* stage pins its fields to random values drawn from their
    declared domains, validated SAT against the prior pins (the later stages are
    still free), retrying a bounded number of times; if no random target is SAT it
    falls back to a constrained uniform ``sample`` of that stage. The final stage
    is served by the ordinary uniform ``sample`` with all prior stages pinned.
    Every step's base is SAT by induction — we only pin values that completed to a
    full model — so a model is always available.

    Returns ``True`` on success (all fields written) or ``None`` if a stage found
    no model (caller should fall back — should not happen, base is SAT)."""
    from dv_solve.bvsat import BVSatCtx, BVSAT_SAT

    sv_by_vid = {vid: (width, lo, hi, signed)
                 for (vid, width, lo, hi, signed) in sample_vars}
    rng = random.Random(seed & _U64)
    pinned = []  # (vid, value, width, signed) accumulated across stages

    def _make_base_pinned(extra):
        """Fresh base with ``pinned + extra`` applied as ``var == value``."""
        b = make_base()
        for pin in pinned + extra:
            b.add_constraint(_pin_eq(b, *pin))
        return b

    def _is_sat(extra):
        b = _make_base_pinned(extra)
        buf, _sz = b.finalize()
        b.destroy()
        bb = BVSatCtx(buf)
        try:
            if solve_info is not None:
                solve_info.n_sat_calls += 1
            return bb.check(seed=rng.randint(0, (1 << 63) - 1),
                            soft_keep=soft_keep) == BVSAT_SAT
        finally:
            bb.destroy()

    stages = [s for s in order_stages if s]
    for si, stage in enumerate(stages):
        is_final = (si == len(stages) - 1)

        if not is_final:
            # Try to assert a random domain target for this stage's fields
            # (the swizzler's assume-random-then-assert).
            pinned_ok = False
            for _ in range(_STAGE_PIN_ATTEMPTS):
                trial = []
                for (f, vid) in stage:
                    width, lo, hi, signed = sv_by_vid[vid]
                    t = rng.randint(lo, hi)
                    trial.append((f, vid, t, width, signed))
                extra = [(vid, t, width, signed)
                         for (_f, vid, t, width, signed) in trial]
                if _is_sat(extra):
                    for (f, vid, t, _w, _s) in trial:
                        f.set_val(t)
                    pinned.extend(extra)
                    pinned_ok = True
                    break
            if pinned_ok:
                continue
            # No random target landed SAT (heavily inter-field-constrained stage):
            # fall through to a constrained sample of just this stage.

        stage_vars = [sv for sv in sample_vars
                      if sv[0] in {vid for (_f, vid) in stage}]
        ok = sample(lambda: _make_base_pinned([]), stage, stage_vars,
                    rng.randint(0, (1 << 63) - 1), solve_info=solve_info,
                    soft_keep=soft_keep)
        if not ok:
            return None
        if not is_final:
            for (f, vid) in stage:
                width, _lo, _hi, signed = sv_by_vid[vid]
                pinned.append((vid, int(f.get_val()), width, signed))

    return True


# --------------------------------------------------------------------------- #
# Distribution-honoring sampling                                                #
# --------------------------------------------------------------------------- #
# A dist-bearing RandSet whose primary path is unavailable (e.g. a dist combined
# with a conjunctive-body implication, which force-routes to the complete BV-SAT
# engine — EF-1b) cannot use the primary's native `add_dist` value picker: the
# BV-SAT engine ignores `add_dist`, and a plain uniform `sample` would wash the
# weighting out to ~uniform (the `test_dist_multiple_dists_in_randset` failure:
# a 99999:1 weighting came out ~50/50). We recover the weighting the same way
# `sample_ordered` recovers solve-order — assume a *weighted* random target for
# each dist field, check SAT, assert it (bounded retry), then uniform-sample the
# remaining (non-dist) fields with the dist pins applied. This mirrors the
# Boolector swizzler's dist handling (pick a weighted value, then constrain the
# rest), reproducing the marginal distribution rather than the joint.


def _weighted_target(entries, rng):
    """Draw one value from a native ``add_dist`` ``DistEntry`` list, honoring the
    weighting. Each entry is ``{lo, hi, weight, is_per_value}``:
      * ``is_per_value`` (``:=`` / single value): every value in ``[lo,hi]`` has
        weight ``weight`` — entry mass ``weight * (hi-lo+1)``.
      * not ``is_per_value`` (``:/``): the range shares ``weight`` collectively —
        entry mass ``weight``.
    Pick an entry proportional to its mass, then a uniform value within it.
    Zero-weight entries have zero mass (the dist exclusion). Returns ``None`` if
    the total mass is zero (all-excluded — caller leaves the field free)."""
    masses = []
    total = 0
    for e in entries:
        span = e["hi"] - e["lo"] + 1
        m = e["weight"] * (span if e["is_per_value"] else 1)
        masses.append(m)
        total += m
    if total <= 0:
        return None
    r = rng.randint(1, total)
    acc = 0
    for e, m in zip(entries, masses):
        acc += m
        if r <= acc:
            return rng.randint(e["lo"], e["hi"])
    last = entries[-1]
    return rng.randint(last["lo"], last["hi"])


def _guard_holds(cond_l):
    """True iff every guard expr in ``cond_l`` currently evaluates true, reading
    the field values already frozen by the guard-pinning pass. Not-aware (the
    if/else builder wraps a false branch in ``ExprUnaryModel(Not, ..)``, which has
    no ``val()``), mirroring ``DvSolveBackend._guard_true``. An unevaluable guard
    is treated as not-held so we never mis-select a branch."""
    from vsc.model.expr_unary_model import ExprUnaryModel
    from vsc.model.unary_expr_type import UnaryExprType

    def _eval(cond):
        if isinstance(cond, ExprUnaryModel) and cond.op == UnaryExprType.Not:
            return not _eval(cond.expr)
        return bool(int(cond.val()))

    try:
        return all(_eval(c) for c in cond_l)
    except Exception:
        return False


def sample_dist_conditional(make_base, readback, sample_vars, seed,
                            cond_dist_targets, guard_vids,
                            solve_info=None, soft_keep=None):
    """Serve a *rand-guarded conditional* dist RandSet via BV-SAT, honoring the
    guard-selected weighting (``if(mode) x dist{A} else x dist{B}``).

    The correct semantics is a phase order — the guard determines which
    distribution applies, so the guard must be resolved first. This function
    stages exactly that:

      1. **Pin guard vars first** (``guard_vids``): draw a random domain value,
         assume→check-SAT→assert, and ``set_val`` the field — the same
         assume-random-then-assert the swizzler / ``sample_ordered`` use. Freezing
         the guards fixes which branch is active for each conditional dist field.
      2. **Per conditional dist field** (``cond_dist_targets`` — ``{vid:
         [(cond_l, entries), ...]}``): find the branches whose guard now holds
         (``_guard_holds``, reading the frozen guard values; a plain dist's empty
         guard always holds) and draw a weighted target from their entries, or
         from their mixture when several hold (``_weighted_target``),
         assume→assert. No active branch → leave the field free (the guarded
         ``inside`` membership still constrains it).
      3. **Uniform-sample the rest** with all pins applied.

    ``guard_vids`` — set of var ids to freeze before branch selection.

    Returns ``True`` on success, or ``None`` if the uniform pass found no model
    (caller falls back — should not happen, the base is SAT)."""
    from dv_solve.bvsat import BVSatCtx, BVSAT_SAT

    sv_by_vid = {vid: (width, lo, hi, signed)
                 for (vid, width, lo, hi, signed) in sample_vars}
    rng = random.Random(seed & _U64)
    pinned = []  # (vid, value, width, signed)

    def _make_base_pinned(extra):
        b = make_base()
        for pin in pinned + extra:
            b.add_constraint(_pin_eq(b, *pin))
        return b

    def _is_sat(extra):
        b = _make_base_pinned(extra)
        buf, _sz = b.finalize()
        b.destroy()
        bb = BVSatCtx(buf)
        try:
            if solve_info is not None:
                solve_info.n_sat_calls += 1
            return bb.check(seed=rng.randint(0, (1 << 63) - 1),
                            soft_keep=soft_keep) == BVSAT_SAT
        finally:
            bb.destroy()

    # 1. Freeze guard vars first (uniform domain draw, assume-then-assert). A guard
    #    whose random targets are all UNSAT is left free — branch selection for the
    #    dependent dist field then finds no active branch and leaves it free too
    #    (membership still holds).
    for (f, vid) in readback:
        if vid not in guard_vids or vid not in sv_by_vid:
            continue
        width, lo, hi, signed = sv_by_vid[vid]
        for _ in range(_STAGE_PIN_ATTEMPTS):
            t = rng.randint(lo, hi)
            pin = (vid, t, width, signed)
            if _is_sat([pin]):
                f.set_val(t)
                pinned.append(pin)
                break

    # 2. Per conditional dist field: pick the active branch (guards now frozen) and
    #    draw a weighted target from it, assume-then-assert.
    for (f, vid) in readback:
        branches = cond_dist_targets.get(vid)
        if not branches or vid not in sv_by_vid:
            continue
        # Several active dists (a plain one is a branch with an empty guard)
        # apply as their equal-probability mixture, as on the constant-guard
        # path (DvSolveBackend._add_dist_for_field).
        active = [br for (cond_l, br) in branches
                  if br and _guard_holds(cond_l)]
        if len(active) > 1:
            from vsc.model.solver.dvsolve_backend import _mix_dist_entries
            entries = _mix_dist_entries(active)
        else:
            entries = active[0] if active else None
        if not entries:
            continue                         # no active branch -> leave field free
        width, lo, hi, signed = sv_by_vid[vid]
        for _ in range(_STAGE_PIN_ATTEMPTS):
            t = _weighted_target(entries, rng)
            if t is None:
                break
            if not (lo <= t <= hi):
                continue
            pin = (vid, t, width, signed)
            if _is_sat([pin]):
                f.set_val(t)
                pinned.append(pin)
                break

    # 3. Uniform-sample everything not yet pinned, with the pins applied.
    pinned_vids = {pin[0] for pin in pinned}
    rest = [(f, vid) for (f, vid) in readback if vid not in pinned_vids]
    if not rest:
        return True
    rest_vars = [sv for sv in sample_vars if sv[0] not in pinned_vids]
    return sample(lambda: _make_base_pinned([]), rest, rest_vars,
                  rng.randint(0, (1 << 63) - 1), solve_info=solve_info,
                  soft_keep=soft_keep)


def sample_dist(make_base, readback, sample_vars, seed, dist_targets,
                solve_info=None, soft_keep=None):
    """Serve a dist-bearing RandSet via BV-SAT while honoring the dist weighting.

    ``dist_targets`` — ``{var_id: [DistEntry, ...]}`` for the dist fields whose
    weighted ``add_dist`` the primary would have applied (captured by the backend
    from ``_add_dist_for_field``).

    For each dist field, draw a weighted target (``_weighted_target``) and
    assume-then-assert it against the prior pins (bounded retry, mirroring the
    swizzler / ``sample_ordered``); if no weighted target lands SAT the field is
    left free for the uniform pass. The remaining non-dist (and any un-pinnable
    dist) fields are then served by the ordinary uniform ``sample`` with the dist
    pins applied.

    Returns ``True`` on success or ``None`` if the uniform pass found no model
    (caller should fall back — should not happen, the base is SAT)."""
    from dv_solve.bvsat import BVSatCtx, BVSAT_SAT

    sv_by_vid = {vid: (width, lo, hi, signed)
                 for (vid, width, lo, hi, signed) in sample_vars}
    rng = random.Random(seed & _U64)
    pinned = []  # (vid, value, width, signed)

    def _make_base_pinned(extra):
        b = make_base()
        for pin in pinned + extra:
            b.add_constraint(_pin_eq(b, *pin))
        return b

    def _is_sat(extra):
        b = _make_base_pinned(extra)
        buf, _sz = b.finalize()
        b.destroy()
        bb = BVSatCtx(buf)
        try:
            if solve_info is not None:
                solve_info.n_sat_calls += 1
            return bb.check(seed=rng.randint(0, (1 << 63) - 1),
                            soft_keep=soft_keep) == BVSAT_SAT
        finally:
            bb.destroy()

    # Weighted assume-then-assert per dist field (in readback order for a stable
    # value stream). A field with no entries, or whose weighted targets are all
    # UNSAT, is left free for the uniform pass below.
    for (f, vid) in readback:
        entries = dist_targets.get(vid)
        if not entries or vid not in sv_by_vid:
            continue
        width, lo, hi, signed = sv_by_vid[vid]
        for _ in range(_STAGE_PIN_ATTEMPTS):
            t = _weighted_target(entries, rng)
            if t is None:
                break
            if not (lo <= t <= hi):
                continue                     # target outside declared domain
            pin = (vid, t, width, signed)
            if _is_sat([pin]):
                f.set_val(t)
                pinned.append(pin)
                break

    pinned_vids = {pin[0] for pin in pinned}
    rest = [(f, vid) for (f, vid) in readback if vid not in pinned_vids]
    if not rest:
        return True
    rest_vars = [sv for sv in sample_vars if sv[0] not in pinned_vids]
    return sample(lambda: _make_base_pinned([]), rest, rest_vars,
                  rng.randint(0, (1 << 63) - 1), solve_info=solve_info,
                  soft_keep=soft_keep)
