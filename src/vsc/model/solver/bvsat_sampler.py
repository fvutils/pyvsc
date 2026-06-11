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
"""
from __future__ import annotations

import random

_U64 = (1 << 64) - 1

# Cap the plane count. A feasible set above 2^_M_CAP cannot be covered by the
# handful of draws a randomize loop makes, so more planes only cost solves.
_M_CAP = 16

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
        acc = None
        for (vid, bit) in bits:
            if rng.getrandbits(1):
                e = b.expr_extract(b.expr_var(vid), bit, bit)
                acc = e if acc is None else b.expr_binary(BIN_BXOR, acc, e)
        if acc is not None:
            r = rng.getrandbits(1)
            b.add_constraint(b.expr_binary(BIN_EQ, acc, b.expr_const(r)))
            return True
    return False


def sample(make_base, readback, sample_vars, seed,
           solve_info=None, m_max=None):
    """Draw a near-uniform model and write it into the readback fields.

    ``make_base``  — zero-arg factory returning a fresh, finalize-ready
                     ``SolveProblemBuilder`` for the base problem (same vars/ids
                     as ``readback``). Invoked exactly once.
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

    def _read(bb, vid):
        ws = _ws.get(vid)
        if ws is None:
            return bb.value(vid)
        width, signed = ws
        if width > 64:
            return bb.value_wide(vid, width, signed)
        # int64 fast path: reinterpret as unsigned for an unsigned field whose
        # top bit is set (only at width 64), matching the field's declared sign.
        v = bb.value(vid)
        return v if signed else v & ((1 << width) - 1)

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
                rc = bb.check(seed=rng.randint(0, (1 << 63) - 1))
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
