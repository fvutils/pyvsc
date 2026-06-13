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

# Use dv-solve's internal BV-SAT completeness engine (zsp_bbsolver, via BVSatCtx)
# as the fallback when the primary bounds-propagation engine can't give an
# authoritative answer (compile-time UNSAT, compile-incomplete, or a search that
# returned no solution). The BV-SAT engine is complete, so it is authoritative
# for both SAT and UNSAT — this is what lets dv-solve stop deferring those cases
# to the external Boolector back-end (Phase A). Set VSC_DVSOLVE_BVSAT=0 to revert
# to the old behavior (defer to Boolector), e.g. to isolate a suspected encoding
# issue. On BVSAT_UNKNOWN/ERROR (an A-4 soundness guard tripped, or a timeout) we
# still defer to the external fallback rather than guess.
_BVSAT_ENABLED = os.environ.get("VSC_DVSOLVE_BVSAT", "1") != "0"

# Whether the BV-SAT engine also *serves* satisfiable fallback problems (writes
# their solved values) — via the uniform sampler (see _BVSAT_SAMPLER) — or only
# decides SAT-vs-UNSAT and lets the external fallback serve SAT for distribution
# quality. Tri-state (VSC_DVSOLVE_BVSAT_SERVE_SAT), F-1a:
#   "0"    — never serve from BV-SAT; defer SAT to the external fallback (the
#            original Phase-A posture, kept as the A/B opt-out).
#   "1"    — always serve SAT from BV-SAT.
#   "auto" — (default) serve SAT from BV-SAT only when there is NO external
#            fallback to serve it (the Randomizer sets _external_fallback_available
#            per-instance from its fallback chain). While Boolector is still the
#            default fallback this is behaviorally identical to "0"; once the
#            fallback is dropped (F-3) dv-solve serves SAT itself with no second
#            flip — so the serve-SAT cost is paid exactly when it buys
#            self-sufficiency (decision §11.2 / F-1a).
# Raw kissat models are too clustered for stimulus (e.g. a uint64 `inside [0..19]`
# left bins 13-15 unhit over 400 draws), which is why serving routes through the
# uniform sampler rather than the raw readback. `force_serve` paths (>64-bit,
# implies-aux) serve regardless of this mode — the primary is not an option there.
def _serve_sat_mode():
    raw = os.environ.get("VSC_DVSOLVE_BVSAT_SERVE_SAT", "auto").lower()
    if raw == "0":
        return "off"
    if raw == "auto":
        return "auto"
    return "on"


_BVSAT_SERVE_SAT_MODE = _serve_sat_mode()

# When BV-SAT serves SAT, route the model through the XOR/parity-hashing uniform
# sampler (bvsat_sampler) instead of reading back kissat's clustered model. This
# is what makes serve-SAT usable for stimulus (see bvsat_sampler.py). On by
# default whenever serve-SAT is on; set VSC_DVSOLVE_BVSAT_SAMPLER=0 to A/B against
# the raw clustered readback.
_BVSAT_SAMPLER = os.environ.get("VSC_DVSOLVE_BVSAT_SAMPLER", "1") != "0"

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
    soft constraints.

    ``dist`` is handled natively (Phase B): each ``ConstraintDistModel`` becomes
    one native ``add_dist`` (weighted, per-value/per-range, zero-weight
    exclusion) on the distributed var, layered on top of the hard ``inside``
    membership that the upstream ``DistConstraintBuilder`` expansion already
    emits (which doubles as the BV-SAT "Domain-Twin" so the completeness engine
    stays sound). Shapes that can't be encoded natively — non-constant weight,
    non-constant/wide range, >64-bit field, multiple dist on one field, or dist
    over array elements — raise ``BackendIncomplete`` and defer to the fallback
    rather than emit a mis-weighted solve."""

    name = "dv-solve"
    supports_soft = True
    supports_dist_native = True
    randomizes_internally = True

    # Whether the Randomizer has an external fallback back-end (Boolector) after
    # this primary. Set per-instance by Randomizer.__init__ once the fallback
    # chain is built; governs the `auto` serve-SAT mode (F-1a). Defaults True so a
    # direct construction (no Randomizer) keeps today's defer-to-fallback posture.
    _external_fallback_available = True

    def _serve_sat_enabled(self) -> bool:
        """Effective serve-SAT decision for this backend instance (F-1a):
        ``"1"`` → always; ``"0"`` → never; ``"auto"`` → only when no external
        fallback is available to serve SAT for distribution. Read at solve time
        so a mid-run mode change (tests) and the per-instance chain both apply."""
        if _BVSAT_SERVE_SAT_MODE == "on":
            return True
        if _BVSAT_SERVE_SAT_MODE == "off":
            return False
        return not self._external_fallback_available  # "auto"

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

        # Distribution (`dist`) is handled natively: _populate_builder emits a
        # native add_dist for each distributed field (see _dist_entries). The
        # un-encodable shapes (§5 of the Phase-B plan) raise BackendIncomplete
        # from there and defer per-RandSet, rather than deferring every dist.

        # Field width vs the engines:
        #  - <=64 bits: the primary bounds-propagation engine (64-bit) handles it
        #    — the optimized common path, unchanged.
        #  - 65..255 bits: the primary engine can't represent it, but the
        #    width-agnostic BV-SAT engine can (Phase D). add_var carries width as
        #    a uint8, so 255 is the hard ceiling.
        #  - >255 bits: not encodable (uint8 width) — defer the whole RandSet.
        # A RandSet with any wide field is routed straight to BV-SAT serving
        # (there is no 64-bit primary path for it); see _build_and_solve.
        for f in rand_fields:
            if f.width > 255:
                raise BackendIncomplete(
                    "dv-solve: field '%s' width %d exceeds 255 bits" % (
                        getattr(f, "name", "?"), f.width),
                    reason_code="width")
        has_wide = any(f.width > 64 for f in rand_fields)

        # ---- Reuse path: an unchanged RandSet re-solves its cached, already
        #      compiled problem (reset + solve) instead of rebuilding it. The
        #      plan is cached on the RandSet's "anchor" field (the lowest-id
        #      rand field) — a persistent model object, so the cache lifetime is
        #      the object's and there is no id()-reuse hazard. ----
        # A solve-order directive (`rand_order_l`) shapes the distribution by
        # solving some fields before others (e.g. solve `a` first, then a value
        # for `c` consistent with it). The BV-SAT uniform sampler has no notion
        # of ordering — it draws from the joint feasible set — so it cannot honor
        # this. When serving SAT for an order-bearing RandSet we therefore defer
        # the *value serving* to the distribution-preserving fallback (Boolector),
        # which honors the order; BV-SAT remains the authoritative UNSAT verdict.
        rand_order_l = getattr(rs, "rand_order_l", None)
        has_order = bool(rand_order_l)

        anchor = min(rand_fields, key=id) if _REUSE_ENABLED else None
        sig = None
        if anchor is not None:
            sig = self._reuse_signature(rs, rand_fields, bound_m)
            plan = getattr(anchor, _PLAN_ATTR, None)
            if plan is not None:
                if plan.struct_sig == sig and plan.values_unchanged():
                    plan.ctx.reset()
                    # The cached SolveCtx keeps its own problem buffer
                    # (SolveCtx._problem); pass it so a non-OK re-solve can fall
                    # back to the BV-SAT engine like the build path.
                    self._solve_and_readback(
                        plan.ctx, plan.readback, randstate, solve_info,
                        problem_buf=getattr(plan.ctx, "_problem", None),
                        has_order=has_order, rand_order_l=rand_order_l)
                    return SolveResult(status=0)
                # Structure or a referenced constant changed: discard and rebuild.
                setattr(anchor, _PLAN_ATTR, None)
                plan.destroy()

        # ---- Build path: translate + compile, then solve. On success the
        #      compiled problem is cached for later reuse. ----
        return self._build_and_solve(
            rs, rand_fields, bound_m, randstate, solve_info, anchor, sig,
            has_order=has_order, has_wide=has_wide, rand_order_l=rand_order_l)

    def _populate_builder(self, b, idmap, rs, rand_fields, bound_m):
        """Declare vars + add hard/soft constraints and domain re-assertions into
        builder ``b`` (using ``idmap`` for var ids). Returns ``(translator,
        sample_vars)`` where ``sample_vars`` is a list of
        ``(var_id, width, lo, hi, is_signed)`` describing each rand field's
        declared domain — consumed by the BV-SAT uniform sampler. Raises
        ``BackendIncomplete`` if a field's domain is outside its width range."""
        from vsc.model.solver.dvsolve_translator import DvSolveExprTranslator

        gapped = []
        sample_vars = []

        # 1. Declare a variable for every rand field, honoring its domain.
        for f in rand_fields:
            vid = idmap.add(f)
            dom = self._domain_of(f, bound_m)
            if dom is None:
                # ``_domain_of`` emptied the field's enclosing range. Two distinct
                # causes — keep them on separate reason codes so the dashboard's
                # "unsat-defer" stays meaningful:
                #  * width > 64: the bound exceeded the int64 ``add_var`` envelope
                #    (a >int64 sub-range can't round-trip through int64). The
                #    problem may well be SAT — we just can't encode the wide bound,
                #    so we defer for the value. Tag `wide-range` (a representation
                #    limit, NOT an unsat).
                #  * width <= 64: the domain is genuinely outside what the field
                #    can represent (e.g. ``a == 500`` on a uint8) — a real
                #    near-unsat the fallback decides authoritatively. Tag
                #    `unsat-defer`.
                reason = "wide-range" if f.width > 64 else "unsat-defer"
                raise BackendIncomplete(
                    "dv-solve: field '%s' domain is outside its %s range" % (
                        getattr(f, "name", "?"),
                        "int64-representable" if f.width > 64 else "width"),
                    reason_code=reason)
            lo, hi, gap_ranges = dom
            b.add_var(vid, f.width, bool(f.is_signed), lo, hi)
            sample_vars.append((vid, int(f.width), lo, hi, bool(f.is_signed)))
            if gap_ranges is not None:
                gapped.append((f, gap_ranges))

        tr = DvSolveExprTranslator(b, idmap)

        # Fields carrying a native `dist`: their weighted add_dist (step 4 below)
        # owns the value picker, so the gap-range *uniform* add_dist must be
        # skipped for them — two add_dist calls on one var would collide (the
        # weighted one is what we want). Their hard membership still comes from
        # the dist's `inside` (in_c) via the normal constraint loop.
        dist_field_m = getattr(rs, "dist_field_m", None) or {}
        dist_fields = set(f for f in dist_field_m if idmap.has(f))

        # 1b. Re-assert any gaps a multi-range/enumerated domain leaves open
        #     (the single [lo,hi] of add_var is only the enclosing range).
        #     The membership constraint guarantees correctness; a uniform
        #     native add_dist over the ranges then makes the value picker
        #     select uniformly *among the feasible values*. Without it,
        #     dv-solve picks uniformly over [lo,hi] and lets the membership
        #     reject misses, which converges hard onto the low end (e.g. a
        #     {0,255} domain came out 0 ~99% of the time).
        for f, gap_ranges in gapped:
            if f in dist_fields:
                continue                     # dist owns this field's add_dist
            b.add_constraint(tr.translate(self._membership_expr(f, gap_ranges)))
            b.add_dist(idmap.id_of(f), [
                {"lo": r[0], "hi": r[1], "weight": 1, "is_per_value": True}
                for r in gap_ranges])

        # 1c. Native dist weighting. The hard `inside` membership twin is
        #     already emitted by the normal constraint loop (DistConstraintBuilder
        #     expansion), satisfying the BV-SAT Domain-Twin Invariant; here we
        #     add only the weighted selection the swizzler would otherwise
        #     supply. Un-encodable shapes raise BackendIncomplete (deferral).
        for f in dist_fields:
            scopes = dist_field_m[f]
            if len(scopes) != 1:
                # Multiple dist on one field: native add_dist composition for
                # repeated calls on one var is unconfirmed; the swizzler picks
                # one per call (not per-seed-invariant). Defer (Phase-B §5).
                raise BackendIncomplete(
                    "dv-solve: multiple dist constraints on field '%s'" %
                    getattr(f, "name", "?"),
                    reason_code="dist")
            if getattr(scopes[0], "is_conditional", False):
                # A conditional dist (inside if/else/implies) applies only when
                # its guard holds. Native add_dist weights the var
                # unconditionally, which would wrongly restrict it when the
                # guard is false — defer to the fallback, which honors the
                # conditional structure (Phase-B §5).
                raise BackendIncomplete(
                    "dv-solve: conditional dist on field '%s'" %
                    getattr(f, "name", "?"),
                    reason_code="dist")
            entries = self._dist_entries(f, scopes[0].dist_c)
            if entries:
                b.add_dist(idmap.id_of(f), entries)

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

        return tr, sample_vars

    def _build_and_solve(self, rs, rand_fields, bound_m, randstate,
                         solve_info, anchor, sig, has_order=False,
                         has_wide=False, rand_order_l=None) -> SolveResult:
        from dv_solve.builder import SolveProblemBuilder
        from dv_solve.ctx import (
            SolveCtx, CompileUnsatError, CompileIncompleteError,
        )
        from vsc.model.solver.var_id_map import VarIdMap

        b = SolveProblemBuilder()
        ctx = None
        cached = False
        try:
            idmap = VarIdMap()
            tr, sample_vars = self._populate_builder(
                b, idmap, rs, rand_fields, bound_m)

            buf, problem_sz = b.finalize()

            # Factory that rebuilds the *same* base problem into a fresh builder
            # (same field order → same var ids). The BV-SAT uniform sampler needs
            # this because kissat is non-incremental: each XOR-hashing attempt
            # rebuilds the base, appends parity planes, and re-finalizes.
            def make_base(_rs=rs, _rf=rand_fields, _bm=bound_m):
                nb = SolveProblemBuilder()
                self._populate_builder(nb, VarIdMap(), _rs, _rf, _bm)
                return nb

            # 4. Compile + solve.
            #
            # Robustness posture: the primary bounds-propagation engine is
            # authoritative for SAT (a found, validated solution is trusted) but
            # NOT for UNSAT/incomplete — a compile-time bound-tightening UNSAT
            # (CompileUnsatError), a construct it can't compile
            # (CompileIncompleteError), or a search that returns no solution may
            # not be a sound proof. Instead of deferring those to the external
            # Boolector back-end, we hand the *same* problem buffer to dv-solve's
            # internal BV-SAT completeness engine, which is complete and therefore
            # authoritative for both SAT and UNSAT (Phase A). Only if it returns
            # UNKNOWN/ERROR do we fall back externally.
            readback = [(f, idmap.id_of(f)) for f in rand_fields]

            # A RandSet the primary engine cannot solve soundly must be served by
            # the complete BV-SAT engine, forced (regardless of the serve-SAT
            # default) since the primary is not an option:
            #  - a >64-bit field has no 64-bit primary path at all (Phase D);
            #  - an aux-lifted logical-combination implication guard makes the
            #    primary's disjunction propagation unsound (F-E3), but the emitted
            #    encoding is correct and BV-SAT is complete (Phase F / F-2).
            # The <=64-bit, primary-sound common path below is unchanged.
            if has_wide or tr.requires_bvsat:
                return self._solve_via_bvsat(
                    buf, readback, randstate, solve_info,
                    make_base=make_base, sample_vars=sample_vars,
                    has_order=has_order, force_serve=True,
                    rand_order_l=rand_order_l)

            try:
                ctx = _make_solve_ctx(buf, problem_sz)
            except (CompileUnsatError, CompileIncompleteError, RuntimeError):
                # Primary can't compile / proves a non-trusted UNSAT -> let the
                # BV-SAT engine decide authoritatively on the same buffer.
                return self._solve_via_bvsat(
                    buf, readback, randstate, solve_info,
                    make_base=make_base, sample_vars=sample_vars,
                    has_order=has_order, rand_order_l=rand_order_l)

            solved_by_primary = self._solve_and_readback(
                ctx, readback, randstate, solve_info, problem_buf=buf,
                make_base=make_base, sample_vars=sample_vars,
                has_order=has_order, rand_order_l=rand_order_l)

            # Retain the compiled ctx for reuse only when the *primary* engine
            # produced the solution — a ctx that needed the BV-SAT fallback is
            # not reusable (it re-solves to the same non-OK result). The plan owns
            # `ctx` (which keeps its own problem buffer alive); it is freed when
            # the plan is evicted (signature change) or its anchor field is
            # garbage-collected.
            if solved_by_primary and anchor is not None and sig is not None:
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

    def _solve_and_readback(self, ctx, readback, randstate, solve_info,
                            problem_buf=None, make_base=None,
                            sample_vars=None, has_order=False,
                            rand_order_l=None) -> bool:
        """Solve ``ctx`` with a fresh seed and write the solved values back into
        the fields. Shared by the build and reuse paths.

        Returns ``True`` if the primary engine solved it (reusable), ``False`` if
        the BV-SAT completeness engine produced the solution instead. On a
        non-OK primary search, falls back to BV-SAT on ``problem_buf`` (when
        provided); BV-SAT UNSAT raises ``SolveFailure``, UNKNOWN/ERROR raises
        ``BackendIncomplete`` (external fallback)."""
        from dv_solve.ctx import SOLVE_OK
        seed = randstate.randint(0, (1 << 63) - 1)
        if solve_info is not None:
            solve_info.n_sat_calls += 1
        # fair_pick=True: uniform marginals / full coverage — the correct
        # distribution for constrained-random stimulus.
        rc = ctx.solve(seed=seed, fair_pick=True)
        if rc == SOLVE_OK:
            # dv-solve returns an int64; for an unsigned field whose value has its
            # top bit set (only at width 64) that int64 is negative, so reinterpret
            # as unsigned. Signed fields are already correctly sign-extended.
            for f, vid in readback:
                f.set_val(self._as_field_value(
                    ctx.get_value(vid), int(f.width), bool(f.is_signed)))
            return True
        # The native *search* is incomplete on some feasible sets that are not
        # simple intervals (e.g. weak backward propagation for extract/bitwise),
        # so a non-OK search result is NOT a sound proof of unsatisfiability.
        # Hand the same problem to the complete BV-SAT engine for an
        # authoritative verdict (or, if it can't decide, defer externally).
        if problem_buf is not None:
            self._solve_via_bvsat(problem_buf, readback, randstate, solve_info,
                                  make_base=make_base, sample_vars=sample_vars,
                                  has_order=has_order, rand_order_l=rand_order_l)
            return False
        raise BackendIncomplete(
            "dv-solve search did not find a solution "
            "(rc=%d); deferring to fallback" % rc,
            reason_code="search-incomplete")

    @staticmethod
    def _as_field_value(raw, width, signed):
        """Reinterpret a raw int64 readback for a field's declared width/sign.
        dv-solve returns an int64; an unsigned field whose value has its top bit
        set (only at width 64) comes back negative, so mask to width. Signed
        fields are already correctly sign-extended."""
        return raw if signed else raw & ((1 << width) - 1)

    @staticmethod
    def _bb_value(bb, vid, sample_vars):
        """Read var ``vid`` from a SAT BVSatCtx, picking the wide (limb-based)
        reader for >64-bit vars and the int64 fast path otherwise, and
        reinterpreting per the field's width/signedness. ``sample_vars`` supplies
        each var's ``(width, is_signed)``."""
        for (svid, width, _lo, _hi, signed) in (sample_vars or ()):
            if svid == vid:
                if width > 64:
                    return bb.value_wide(vid, width, signed)
                return DvSolveBackend._as_field_value(bb.value(vid), width, signed)
        return bb.value(vid)

    @staticmethod
    def _order_stages(readback, rand_order_l):
        """Group ``readback`` ``[(field, vid)]`` into solve-order stages from
        ``rand_order_l`` (a list of field lists, earliest-solved first), appending
        a final stage for any rand fields not named in an order group. Returns the
        list of ``[(field, vid)]`` stages (partitioning every rand field exactly
        once), or ``None`` when there is no usable ordering. A single resulting
        stage is fine — ``sample_ordered`` degrades to a plain uniform sample."""
        if not rand_order_l:
            return None
        f2vid = {f: vid for (f, vid) in readback}
        stages = []
        seen = set()
        for grp in rand_order_l:
            stage = [(f, f2vid[f]) for f in grp if f in f2vid]
            if stage:
                stages.append(stage)
                seen.update(f for (f, _v) in stage)
        rest = [(f, vid) for (f, vid) in readback if f not in seen]
        if rest:
            stages.append(rest)
        return stages or None

    def _solve_via_bvsat(self, problem_buf, readback, randstate,
                         solve_info, make_base=None, sample_vars=None,
                         has_order=False, force_serve=False,
                         rand_order_l=None) -> SolveResult:
        """Solve ``problem_buf`` with the internal BV-SAT completeness engine and
        write values back. Authoritative: SAT -> set values & return; UNSAT ->
        ``SolveFailure``; UNKNOWN/ERROR (A-4 guard / timeout) -> ``BackendIncomplete``
        so the external fallback decides. Honors ``VSC_DVSOLVE_BVSAT=0``.

        When serving SAT (``_serve_sat_enabled()`` — i.e. mode ``1``/``auto``
        with no external fallback — or ``force_serve``) and a ``make_base``
        factory is available, the model is drawn through the
        XOR-hashing uniform sampler (``bvsat_sampler``) so the value distribution
        is usable as stimulus; otherwise the raw (clustered) kissat model is read
        back. ``force_serve`` is set for >64-bit RandSets, which have no other
        engine to serve them."""
        if not _BVSAT_ENABLED:
            raise BackendIncomplete(
                "dv-solve primary could not decide; BV-SAT disabled, deferring",
                reason_code="bvsat-disabled")
        from dv_solve.bvsat import BVSatCtx, BVSAT_SAT, BVSAT_UNSAT
        seed = randstate.randint(0, (1 << 63) - 1)
        if solve_info is not None:
            solve_info.n_sat_calls += 1
        bb = BVSatCtx(problem_buf)
        try:
            rc = bb.check(seed=seed)
            if rc == BVSAT_UNSAT:
                # Complete engine -> sound UNSAT. dv-solve is now authoritative
                # for UNSAT without needing the external fallback. The Randomizer
                # catches this and re-raises with its own (Boolector-built)
                # diagnostics, so the message here is internal.
                raise SolveFailure(
                    "dv-solve BV-SAT engine proved unsatisfiable",
                    "dv-solve BV-SAT engine proved the constraints unsatisfiable")
            if rc == BVSAT_SAT and (self._serve_sat_enabled() or force_serve):
                # Prefer the uniform sampler: kissat's raw model is too clustered
                # for stimulus. The base SAT verdict above guarantees the sampler
                # converges (m==0 is this same satisfiable problem).
                from vsc.model.solver import bvsat_sampler
                if has_order:
                    # Honor `solve_order` natively via *staged* sampling: freeze
                    # each order stage's values before sampling the next, matching
                    # the Boolector swizzler's per-stage assume/assert. Only when
                    # we can serve it natively — sampler available and every
                    # ordered field's domain fits the int64 freeze carrier;
                    # otherwise fall through to the distribution-preserving
                    # fallback (the prior behavior for order-bearing RandSets).
                    stages = self._order_stages(readback, rand_order_l)
                    if (_BVSAT_SAMPLER and make_base is not None and sample_vars
                            and stages is not None
                            and bvsat_sampler.stage_sampleable(sample_vars)):
                        ok = bvsat_sampler.sample_ordered(
                            make_base, stages, sample_vars, seed,
                            solve_info=solve_info)
                        if ok:
                            return SolveResult(status=0)
                    # Not natively serveable in order → defer (raise below).
                else:
                    if _BVSAT_SAMPLER and make_base is not None and sample_vars:
                        ok = bvsat_sampler.sample(
                            make_base, readback, sample_vars, seed,
                            solve_info=solve_info)
                        if ok:
                            return SolveResult(status=0)
                        # Sampler couldn't serve (shouldn't happen): fall through
                        # to the raw readback so we still return a valid model.
                    for f, vid in readback:
                        f.set_val(self._bb_value(bb, vid, sample_vars))
                    return SolveResult(status=0)
            # Two distinct deferrals share this exit — keep their reason codes
            # SEPARATE so the burn-down dashboard's correctness signal is honest:
            #
            #  * rc == BVSAT_SAT: the problem IS satisfiable (BV-SAT proved it),
            #    but we are not serving it here — either serve-SAT is off and
            #    BV-SAT's model is too clustered for stimulus, or the RandSet is
            #    order-bearing AND not natively stage-sampleable (a wide /
            #    unsigned-64 ordered field whose domain overflows the int64 freeze
            #    carrier — staged serving handles the common narrow case above).
            #    Defer to the distribution-preserving fallback to pick the values.
            #    This is EXPECTED, correct operation of the two-engine
            #    architecture, not a completeness gap — tag `bvsat-sat-deferred`.
            #  * rc == UNKNOWN/ERROR: an A-4 guard tripped or the engine genuinely
            #    could not decide. This is the real completeness gap the dashboard
            #    must drive to zero — tag it `bvsat-undecided`.
            if rc == BVSAT_SAT:
                raise BackendIncomplete(
                    "dv-solve BV-SAT proved SAT but is not serving it "
                    "(distribution / solve_order); deferring to fallback",
                    reason_code="bvsat-sat-deferred")
            raise BackendIncomplete(
                "dv-solve BV-SAT verdict=%d (undecided); deferring to fallback"
                % rc,
                reason_code="bvsat-undecided")
        finally:
            bb.destroy()

    def _reuse_signature(self, rs, rand_fields, bound_m):
        """A structural fingerprint of the compiled problem. Two RandSets with
        equal signatures (and unchanged referenced non-rand values) compile to
        the same problem, so a cached plan may be reused. Captures: each rand
        field's identity/width/signedness and domain (incl. multi-range gaps),
        the identity (and priority) of every hard/soft constraint, and each
        ``dist`` scope's weight entries. Inline ``randomize_with`` builds fresh
        constraint objects each call → different ids → automatic miss."""
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
        # dist weights bake into the compiled add_dist but aren't expressed as
        # constraints, so capture each entry's (lo, hi, weight, is_per_value).
        # A dynamic weight (e.g. weight(1, en_one)) changes the problem without
        # any constraint id changing; without this a stale compiled problem
        # would be reused. Mirrors the Tier-A _snapshot_dist signature.
        dist_sig = self._dist_signature(rs)
        return (field_sig, tuple(dom_sig), cons_sig, soft_sig, dist_sig)

    @staticmethod
    def _dist_signature(rs):
        """Snapshot of every dist scope's weight entries for reuse keying, or a
        marker that can't compare equal if a weight/range can't be evaluated
        (forcing a rebuild)."""
        dist_field_m = getattr(rs, "dist_field_m", None) or {}
        sig = []
        for f in dist_field_m:
            for scope in dist_field_m[f]:
                entry = []
                for w in scope.dist_c.weights:
                    try:
                        lo = int(w.rng_lhs.val())
                        hi = int(w.rng_rhs.val()) if w.rng_rhs is not None else lo
                        wt = int(w.weight.val())
                        entry.append((lo, hi, wt,
                                      bool(getattr(w, "is_per_value", lo == hi))))
                    except Exception:
                        # Unevaluable -> a unique object so signatures never match
                        # (always rebuild rather than risk a stale problem).
                        entry.append(object())
                sig.append((id(f), tuple(entry)))
        return tuple(sig)

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

        # add_var carries bounds as int64. For width > 64 the width-range
        # overflows int64, so clamp to the int64 envelope: the BV-SAT engine
        # treats a wide var's bound == its (int64-capped) natural range as "no
        # bound asserted" (assert_var_bounds caps natural_hi at INT64_MAX for
        # width>=64), leaving the var free across its true width — correct for an
        # unconstrained wide field. A genuine >64-bit sub-range can't round-trip
        # through int64; its membership constraint would carry a >64-bit literal
        # and defer (see the translator's literal guard).
        # For width <= 64 we must NOT clamp: a full-range uint64 [0, 2^64-1] is
        # passed through as c_int64 wrapping 2^64-1 -> -1, which the engine reads
        # (unsigned) as the full range. Clamping it to INT64_MAX would halve a
        # uint64 field's domain.
        if f.width > 64:
            _I64_MIN, _I64_MAX = -(1 << 63), (1 << 63) - 1
            w_lo = max(w_lo, _I64_MIN)
            w_hi = min(w_hi, _I64_MAX)

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

    # int64 / uint32 envelopes for native DistEntry fields (lo/hi int64,
    # weight uint32). A dist outside these can't be encoded → defer.
    _I64_MIN = -(1 << 63)
    _I64_MAX = (1 << 63) - 1
    _U32_MAX = (1 << 32) - 1

    def _dist_entries(self, field, dist_c):
        """Translate a ``ConstraintDistModel`` into native ``add_dist``
        ``DistEntry`` dicts.

        Each ``DistWeightExprModel`` becomes one entry: a single value → a
        ``[v, v]`` per-value entry; a range → a ``[lo, hi]`` entry whose
        ``is_per_value`` follows the ``:=``/``:/`` flag. Zero-weight entries are
        kept so native does the exclusion. Raises ``BackendIncomplete`` for any
        shape that can't be encoded soundly (Phase-B §5): non-constant
        weight/range, a bound outside int64, or a >64-bit field (the BV-SAT
        completeness engine ignores ``add_dist``, so weighting a wide field would
        be silently lost)."""
        if field.width > 64:
            raise BackendIncomplete(
                "dv-solve: dist on >64-bit field '%s' not supported" %
                getattr(field, "name", "?"),
                reason_code="dist")
        entries = []
        for w in dist_c.weights:
            try:
                lo = int(w.rng_lhs.val())
                if w.rng_rhs is not None:
                    hi = int(w.rng_rhs.val())
                    is_per_value = bool(w.is_per_value)
                else:
                    hi = lo
                    is_per_value = True       # single value: := and :/ coincide
                weight = int(w.weight.val())
            except Exception:
                raise BackendIncomplete(
                    "dv-solve: dist on '%s' has a non-constant weight or range" %
                    getattr(field, "name", "?"),
                    reason_code="dist")
            if not (self._I64_MIN <= lo <= self._I64_MAX
                    and self._I64_MIN <= hi <= self._I64_MAX):
                raise BackendIncomplete(
                    "dv-solve: dist range on '%s' exceeds int64" %
                    getattr(field, "name", "?"),
                    reason_code="dist")
            if not (0 <= weight <= self._U32_MAX):
                raise BackendIncomplete(
                    "dv-solve: dist weight on '%s' out of uint32 range" %
                    getattr(field, "name", "?"),
                    reason_code="dist")
            if hi < lo:
                lo, hi = hi, lo
            entries.append({"lo": lo, "hi": hi, "weight": weight,
                            "is_per_value": is_per_value})
        return entries
