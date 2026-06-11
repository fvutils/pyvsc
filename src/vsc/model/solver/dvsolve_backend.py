# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# Created on Jun 9, 2026
#
# dv-solve solver back-end (plan P1-3, design §4.2/§4.4). Translates a RandSet
# into a dv-solve problem, solves it with a seed derived from pyvsc's RandState,
# and writes the solved values back into the fields.

import os
from typing import Dict

from vsc.model.solver.backend import SolverBackendIF, SolveResult, BackendIncomplete
from vsc.model.solve_failure import SolveFailure


# Reuse the compiled dv-solve problem across randomizations of the same object
# ("compile once, solve many") — ~2x end-to-end throughput. Reuse is transparent:
# reset()+solve(seed) is bit-identical to a fresh compile+solve(seed), the value
# stream and distribution are unchanged, and the full ve/unit suite passes. Set
# VSC_DVSOLVE_REUSE=0 to disable (e.g. to isolate a suspected stale-cache issue).
_REUSE_ENABLED = os.environ.get("VSC_DVSOLVE_REUSE", "1") != "0"

# Attribute under which a RandSet's compiled plan is cached on its anchor field.
_PLAN_ATTR = "_dvsolve_plan"


class _CompiledPlan(object):
    """A built+compiled dv-solve problem retained for reuse.

    Holds the native resources (builder buffer + SolveCtx) alive and the data
    needed to (a) decide whether it is still valid for a later RandSet and
    (b) read solved values back. Reuse = ``ctx.reset()`` + ``ctx.solve(seed)``
    instead of rebuilding and recompiling from scratch.
    """

    __slots__ = ("ctx", "readback", "struct_sig", "const_fields", "_keepalive")

    def __init__(self, ctx, readback, struct_sig, const_fields, keepalive):
        # The ctx keeps its own SolveProblem buffer alive (SolveCtx._problem),
        # so the builder is transient and need not be retained here.
        self.ctx = ctx                      # the compiled SolveCtx
        self.readback = readback            # list of (field, var_id)
        self.struct_sig = struct_sig        # structural reuse signature
        self.const_fields = const_fields    # list of (non-rand field, value)
        # Hold strong references to the constraint objects whose id()s appear in
        # struct_sig. Without this, a transient constraint (e.g. the per-iteration
        # soft ConstraintSoftModel that coverage steering builds) is GC'd after
        # the solve, Python recycles its id for the next iteration's constraint,
        # and the signature *falsely matches* → a stale plan is reused. Keeping
        # the objects alive makes every id() unique for the plan's lifetime.
        self._keepalive = keepalive

    def values_unchanged(self):
        """True iff every referenced non-rand field still holds the value that
        was baked into the compiled problem as a constant."""
        for f, v in self.const_fields:
            if int(f.val) != v:
                return False
        return True

    def destroy(self):
        ctx = self.ctx
        self.ctx = None
        if ctx is not None:
            try:
                ctx.destroy()
            except Exception:
                pass

    def __del__(self):
        self.destroy()


# The solver's static pool (compiled-problem storage) is bump-allocated in a
# caller-supplied buffer and hard-fails on overflow (no spill to the block
# allocator). The old fixed 1 MiB default was oversized legacy headroom — and it
# doubled as the block-allocator *block size*, so every dynamic block was 1 MiB
# too: allocating+zeroing it per compile cost ~half the no-cache time. We instead
# *size the buffer from the problem*: empirically the pool need is ~a 64 KiB floor
# plus ~20-30x the serialized problem size, so 40x is a safe first estimate. A
# grow-on-overflow loop is the safety net for any under-estimate. (The clean
# long-term fix is a truly dynamic pool — see plan §6 B1.)
_CTX_BUF_FLOOR = 64 * 1024
_CTX_BUF_MAX = 16 * 1024 * 1024
_CTX_BUF_PER_PROBLEM_BYTE = 40


def _make_solve_ctx(buf, problem_sz=0):
    """Create a SolveCtx with a problem-sized working-pool buffer, growing on
    pool overflow. Compile *verdicts* (UNSAT / incomplete) are real and not
    retried; a generic compile failure (likely pool overflow) is retried at 4x
    until ``_CTX_BUF_MAX``, then propagates."""
    from dv_solve.ctx import (
        SolveCtx, CompileUnsatError, CompileIncompleteError)
    # First estimate from the problem, rounded up to a 64 KiB multiple.
    size = max(_CTX_BUF_FLOOR,
               (problem_sz * _CTX_BUF_PER_PROBLEM_BYTE + 0xFFFF) & ~0xFFFF)
    last = None
    while size <= _CTX_BUF_MAX:
        try:
            return SolveCtx(buf, ctx_buf_size=size)
        except (CompileUnsatError, CompileIncompleteError):
            raise
        except RuntimeError as e:
            last = e   # likely pool overflow — grow and retry
            size *= 4
    raise last if last is not None else RuntimeError("solver pool sizing failed")


class DvSolveBackend(SolverBackendIF):
    """Native dv-solve back-end. Randomizes internally (no swizzler) and honors
    soft constraints. ``dist`` is handled natively in Phase 2; for now it is
    expanded upstream like the Boolector path (``supports_dist_native`` False)."""

    name = "dv-solve"
    supports_soft = True
    supports_dist_native = False
    randomizes_internally = True

    @classmethod
    def available(cls) -> bool:
        try:
            from dv_solve.lib import _load_lib
        except ImportError:
            return False
        # The Phase-1 back-end needs the native library; the pure-Python engine
        # (Phase 3) will relax this.
        try:
            return _load_lib() is not None
        except Exception:
            return False

    def solve_randset(self,
                      rs,
                      bound_m: Dict,
                      randstate,
                      solve_info=None,
                      debug=0) -> SolveResult:
        rand_fields = rs.rand_fields()

        # An empty rand set has nothing to solve.
        if len(rand_fields) == 0:
            return SolveResult(status=0)

        # Distribution (`dist`) weighting is applied by the Boolector swizzler,
        # which this back-end skips (it randomizes internally). Until native
        # `dist` lands (supports_dist_native), defer any RandSet carrying dist
        # weights to the fallback so the weighted distribution is honored — the
        # dv-solve path would otherwise satisfy the ranges but ignore the weights.
        if getattr(rs, "dist_field_m", None):
            raise BackendIncomplete(
                "dv-solve: dist weighting not yet native; deferring to fallback")

        # dv-solve's variables (and modular propagators) are 64-bit; its add_var
        # width is a uint8. Anything wider can't be encoded soundly, so defer the
        # whole RandSet to the fallback back-end.
        for f in rand_fields:
            if f.width > 64:
                raise BackendIncomplete(
                    "dv-solve: field '%s' width %d exceeds 64 bits" % (
                        getattr(f, "name", "?"), f.width))

        # ---- Reuse path: an unchanged RandSet re-solves its cached, already
        #      compiled problem (reset + solve) instead of rebuilding it. The
        #      plan is cached on the RandSet's "anchor" field (the lowest-id
        #      rand field) — a persistent model object, so the cache lifetime is
        #      the object's and there is no id()-reuse hazard. ----
        anchor = min(rand_fields, key=id) if _REUSE_ENABLED else None
        sig = None
        if anchor is not None:
            sig = self._reuse_signature(rs, rand_fields, bound_m)
            plan = getattr(anchor, _PLAN_ATTR, None)
            if plan is not None:
                if plan.struct_sig == sig and plan.values_unchanged():
                    plan.ctx.reset()
                    self._solve_and_readback(
                        plan.ctx, plan.readback, randstate, solve_info)
                    return SolveResult(status=0)
                # Structure or a referenced constant changed: discard and rebuild.
                setattr(anchor, _PLAN_ATTR, None)
                plan.destroy()

        # ---- Build path: translate + compile, then solve. On success the
        #      compiled problem is cached for later reuse. ----
        return self._build_and_solve(
            rs, rand_fields, bound_m, randstate, solve_info, anchor, sig)

    def _build_and_solve(self, rs, rand_fields, bound_m, randstate,
                         solve_info, anchor, sig) -> SolveResult:
        from dv_solve.builder import SolveProblemBuilder
        from dv_solve.ctx import (
            SolveCtx, CompileUnsatError, CompileIncompleteError,
        )
        from vsc.model.solver.var_id_map import VarIdMap
        from vsc.model.solver.dvsolve_translator import DvSolveExprTranslator

        b = SolveProblemBuilder()
        ctx = None
        cached = False
        try:
            idmap = VarIdMap()
            gapped = []

            # 1. Declare a variable for every rand field, honoring its domain.
            for f in rand_fields:
                vid = idmap.add(f)
                dom = self._domain_of(f, bound_m)
                if dom is None:
                    # Field's domain is outside its representable range; defer
                    # the authoritative SAT/UNSAT verdict to the fallback.
                    raise BackendIncomplete(
                        "dv-solve: field '%s' domain is outside its width range" %
                        getattr(f, "name", "?"))
                lo, hi, gap_ranges = dom
                b.add_var(vid, f.width, bool(f.is_signed), lo, hi)
                if gap_ranges is not None:
                    gapped.append((f, gap_ranges))

            tr = DvSolveExprTranslator(b, idmap)

            # 1b. Re-assert any gaps a multi-range/enumerated domain leaves open
            #     (the single [lo,hi] of add_var is only the enclosing range).
            #     The membership constraint guarantees correctness; a uniform
            #     native add_dist over the ranges then makes the value picker
            #     select uniformly *among the feasible values*. Without it,
            #     dv-solve picks uniformly over [lo,hi] and lets the membership
            #     reject misses, which converges hard onto the low end (e.g. a
            #     {0,255} domain came out 0 ~99% of the time).
            for f, gap_ranges in gapped:
                b.add_constraint(tr.translate(self._membership_expr(f, gap_ranges)))
                b.add_dist(idmap.id_of(f), [
                    {"lo": r[0], "hi": r[1], "weight": 1, "is_per_value": True}
                    for r in gap_ranges])

            # 2. Hard constraints.
            for c in rs.constraints():
                b.add_constraint(tr.translate(c))

            # 3. Soft constraints. pyvsc's effective preference is (higher
            #    .priority first, ties broken by declaration order); dv-solve
            #    honors *lower* priority numbers first. Assign dv priorities by
            #    that preference rank so both back-ends relax in the same order.
            softs = rs.soft_constraints()
            if len(softs) > 0:
                order = sorted(range(len(softs)),
                               key=lambda i: (-softs[i].priority, i))
                for dv_pri, i in enumerate(order):
                    b.add_soft_constraint(tr.translate(softs[i]), dv_pri)

            buf, problem_sz = b.finalize()

            # 4. Compile + solve.
            #
            # Robustness posture: dv-solve is authoritative for SAT (a found,
            # validated solution is trusted) but NOT for UNSAT. A dv-solve UNSAT
            # verdict — whether compile-time bound tightening (CompileUnsatError)
            # or search (SOLVE_UNSAT) — depends on the encoding being faithful
            # and the search being complete, neither of which we fully trust yet
            # for the dv-solve path. So *every* dv-solve "no solution" outcome
            # defers to the fallback back-end, which gives the definitive answer
            # (it reports a genuine SolveFailure only if the problem truly is
            # UNSAT). This costs an extra solve on the rare UNSAT but prevents a
            # translator/engine quirk from surfacing as a spurious failure.
            try:
                ctx = _make_solve_ctx(buf, problem_sz)
            except CompileUnsatError:
                raise BackendIncomplete(
                    "dv-solve reports compile-time UNSAT; deferring to fallback")
            except CompileIncompleteError:
                # A construct the engine can't compile natively; fall back.
                raise BackendIncomplete("dv-solve could not compile the problem")
            except RuntimeError:
                # Even the largest pool buffer couldn't compile it; fall back
                # rather than surfacing a hard error.
                raise BackendIncomplete("dv-solve could not size the solver pool")

            readback = [(f, idmap.id_of(f)) for f in rand_fields]
            self._solve_and_readback(ctx, readback, randstate, solve_info)

            # Solve succeeded → retain the compiled ctx for reuse. The plan owns
            # `ctx` (which keeps its own problem buffer alive); it is freed when
            # the plan is evicted (signature change) or its anchor field is
            # garbage-collected.
            if anchor is not None and sig is not None:
                # Keep the constraint objects whose ids are in `sig` alive so
                # Python can't recycle a freed id into the next RandSet and cause
                # a false signature match (see _CompiledPlan._keepalive).
                keepalive = (list(rs.constraints()), list(rs.soft_constraints()))
                plan = _CompiledPlan(
                    ctx, readback, sig, list(tr.const_fields.items()), keepalive)
                setattr(anchor, _PLAN_ATTR, plan)
                cached = True

            return SolveResult(status=0)
        finally:
            # The builder is transient — finalize() produced a self-contained,
            # Python-owned buffer, so the builder is never needed past this call.
            b.destroy()
            if not cached and ctx is not None:
                # Build/compile/solve failed (or caching disabled): free the ctx.
                ctx.destroy()

    def _solve_and_readback(self, ctx, readback, randstate, solve_info):
        """Solve ``ctx`` with a fresh seed and write the solved values back into
        the fields. Shared by the build and reuse paths. Raises
        ``BackendIncomplete`` on any non-OK outcome so the Randomizer falls back
        (dv-solve is authoritative for SAT only)."""
        from dv_solve.ctx import SOLVE_OK
        seed = randstate.randint(0, (1 << 63) - 1)
        if solve_info is not None:
            solve_info.n_sat_calls += 1
        # fair_pick=True: uniform marginals / full coverage — the correct
        # distribution for constrained-random stimulus.
        rc = ctx.solve(seed=seed, fair_pick=True)
        if rc != SOLVE_OK:
            # The native *search* is incomplete on some feasible sets that are
            # not simple intervals (e.g. weak backward propagation for
            # extract/bitwise), so a SOLVE_UNSAT from search is NOT a sound proof
            # of unsatisfiability — only a compile-time CompileUnsatError is.
            # Defer to the fallback (it reports a genuine SolveFailure if the
            # problem really is UNSAT).
            raise BackendIncomplete(
                "dv-solve search did not find a solution "
                "(rc=%d); deferring to fallback" % rc)
        # dv-solve returns a signed int64 already adjusted for the variable's
        # signedness, so no manual sign-extension is needed (unlike Boolector).
        for f, vid in readback:
            f.set_val(ctx.get_value(vid))

    def _reuse_signature(self, rs, rand_fields, bound_m):
        """A structural fingerprint of the compiled problem. Two RandSets with
        equal signatures (and unchanged referenced non-rand values) compile to
        the same problem, so a cached plan may be reused. Captures: each rand
        field's identity/width/signedness and domain (incl. multi-range gaps),
        and the identity (and priority) of every hard/soft constraint. Inline
        ``randomize_with`` builds fresh constraint objects each call → different
        ids → automatic miss."""
        field_sig = tuple((id(f), int(f.width), bool(f.is_signed))
                          for f in rand_fields)
        dom_sig = []
        for f in rand_fields:
            dom = self._domain_of(f, bound_m)
            if dom is None:
                dom_sig.append((id(f), None))
            else:
                lo, hi, gaps = dom
                dom_sig.append((id(f), lo, hi,
                                tuple(map(tuple, gaps)) if gaps else None))
        cons_sig = tuple(id(c) for c in rs.constraints())
        soft_sig = tuple((id(c), c.priority) for c in rs.soft_constraints())
        return (field_sig, tuple(dom_sig), cons_sig, soft_sig)

    # ------------------------------------------------------------------ #
    # Domain helpers                                                       #
    # ------------------------------------------------------------------ #

    def _domain_of(self, f, bound_m):
        """Return ``(lo, hi, gap_ranges)`` for a field, clamped to the field's
        representable (width-based) range.

        ``lo``/``hi`` are the enclosing range passed to ``add_var``;
        ``gap_ranges`` is the multi-range list when the domain has gaps (so the
        backend can re-assert membership), else ``None``.

        Clamping is essential: a constraint like ``a == 500`` makes
        ``VariableBoundVisitor`` report a domain of ``[500, 500]`` even for a
        uint8 field, but 500 is not 8-bit representable, so the field truly
        cannot satisfy it (Boolector reports UNSAT). Without clamping, dv-solve
        would declare the variable over ``[500, 500]`` and "solve" it to an
        impossible value. If clamping empties the range, this returns ``None`` to
        signal the caller to defer to the fallback (which gives the authoritative
        SAT/UNSAT answer)."""
        if f.is_signed:
            w_lo = -(1 << (f.width - 1))
            w_hi = (1 << (f.width - 1)) - 1
        else:
            w_lo = 0
            w_hi = (1 << f.width) - 1

        bound = bound_m.get(f) if bound_m is not None else None
        range_l = bound.domain.range_l if bound is not None else None

        if not range_l:
            return w_lo, w_hi, None

        lo = max(min(r[0] for r in range_l), w_lo)
        hi = min(max(r[1] for r in range_l), w_hi)
        if lo > hi:
            # Domain lies entirely outside what the field can represent ->
            # unsatisfiable at this width; let the fallback decide.
            return None
        gap_ranges = range_l if len(range_l) > 1 else None
        return lo, hi, gap_ranges

    def _membership_expr(self, field, range_l):
        """Build an ``inside`` expression asserting ``field`` lies within one of
        ``range_l``'s ranges. Translating it yields the OR-of-(>= && <=)
        comparison form the native compiler accepts (it rejects an OR of
        expr_in_range leaves), and reuses the shared idmap for the field's var."""
        from vsc.model.expr_fieldref_model import ExprFieldRefModel
        from vsc.model.expr_in_model import ExprInModel
        from vsc.model.expr_rangelist_model import ExprRangelistModel
        from vsc.model.expr_range_model import ExprRangeModel
        from vsc.model.expr_literal_model import ExprLiteralModel

        rl = ExprRangelistModel([
            ExprRangeModel(
                ExprLiteralModel(r[0], bool(field.is_signed), field.width),
                ExprLiteralModel(r[1], bool(field.is_signed), field.width))
            for r in range_l])
        return ExprInModel(ExprFieldRefModel(field), rl)
