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

from vsc.model.solver.backend import (
    SolverBackendIF, SolveResult, BackendIncomplete, BackendInternalError)
from vsc.model.solve_failure import SolveFailure
from vsc.model.model_visitor import ModelVisitor
from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.constraint_scope_model import ConstraintScopeModel
from vsc.model.constraint_if_else_model import ConstraintIfElseModel
from vsc.model.constraint_implies_model import ConstraintImpliesModel
from vsc.model import phase_timers as PT
from vsc.model import opt_flags


class _RefsUsedRandVisitor(ModelVisitor):
    """Detect whether a constraint (sub)tree references any *used-rand* field. A
    hard constraint that references none is fully constant at the current field
    values (e.g. every referenced field is non-rand, or a ``rand_mode(0)``
    disabled rand field)."""

    def __init__(self):
        super().__init__()
        self.found = False

    def visit_expr_fieldref(self, e):
        if getattr(e.fm, "is_used_rand", False):
            self.found = True


def _refs_used_rand(c) -> bool:
    v = _RefsUsedRandVisitor()
    c.accept(v)
    return v.found


def _const_constraint_holds(c):
    """Boolean truth of a fully-constant hard constraint (one that references no
    used-rand field, so every operand is a constant at its current value).

    Returns True/False when the shape can be evaluated, or ``None`` when it can't
    (the caller then leaves it to the solver, unchanged — never a false UNSAT).

    Mirrors Boolector, which evaluates such a constraint and reports UNSAT when it
    is false. dv-solve's builder drops variable-free constraints, so without this
    a violated constant constraint (a disabled field whose fixed value breaks its
    own constraint) would be silently ignored."""
    try:
        if isinstance(c, ConstraintExprModel):
            return int(c.e.val()) != 0
        if isinstance(c, ConstraintIfElseModel):
            if int(c.cond.val()) != 0:
                return _const_constraint_holds(c.true_c)
            return True if c.false_c is None else _const_constraint_holds(c.false_c)
        if isinstance(c, ConstraintImpliesModel):
            # ConstraintImpliesModel is a scope with a guard: (!cond) || body.
            if int(c.cond.val()) == 0:
                return True
            return _scope_holds(c)
        if isinstance(c, ConstraintScopeModel):
            return _scope_holds(c)
    except Exception:
        return None
    return None


def _scope_holds(scope):
    """AND of a scope's child constraints, all constant. ``None`` if any child is
    non-evaluable."""
    for cc in scope.constraint_l:
        r = _const_constraint_holds(cc)
        if r is None:
            return None
        if r is False:
            return False
    return True


def _check_const_constraints(rs):
    """Raise ``SolveFailure`` if any hard constraint of ``rs`` is fully constant
    and false. A constant-false hard constraint makes the RandSet unsatisfiable;
    dv-solve's builder would otherwise drop it (it has no variable), so we honor
    it here to match Boolector."""
    for c in rs.constraints():
        if not _refs_used_rand(c) and _const_constraint_holds(c) is False:
            raise SolveFailure(
                "solve failure",
                "unsatisfiable constant constraint (all operands fixed)")


# Reuse the compiled dv-solve problem across randomizations of the same object
# ("compile once, solve many") — ~2x end-to-end throughput. Reuse is transparent:
# reset()+solve(seed) is bit-identical to a fresh compile+solve(seed), the value
# stream and distribution are unchanged, and the full ve/unit suite passes. Set
# VSC_DVSOLVE_REUSE=0 to disable (e.g. to isolate a suspected stale-cache issue).
# Widest field dv-solve solves: the engine's DVS_MAX_WIDTH (2^24 bits since
# widths went 32-bit, v2 plan V26). Fields over 64 bits are served by BV-SAT.
# A dv-solve without dvs_max_width() carries widths as a uint16.
def _engine_max_width():
    try:
        from dv_solve.lib import max_width
        return max_width() or 65535
    except (ImportError, AttributeError, OSError):
        return 65535


_MAX_FIELD_WIDTH = _engine_max_width()

_REUSE_ENABLED = os.environ.get("VSC_DVSOLVE_REUSE", "1") != "0"

# Cap on the total variable count of a whole-problem merged solve (see
# solve_merged / _build_merged). Merging independent partitions into one native
# solve wins by eliminating per-RandSet Python overhead, but the merged native
# solve degrades super-linearly past a few hundred vars (measured cliff ~256→384),
# so above this cap the per-RandSet path (linear) is used instead.
_MERGE_MAX_VARS = int(os.environ.get("VSC_DVSOLVE_MERGE_MAX_VARS", "256"))

# When the primary bounds-propagation engine can't give an authoritative answer
# (compile-time UNSAT, compile-incomplete, or a search that returned no
# solution), dv-solve's internal BV-SAT completeness engine (zsp_bbsolver, via
# BVSatCtx) decides the RandSet and serves it: complete, so authoritative for
# both SAT and UNSAT. Raw kissat models are too clustered for stimulus (e.g. a
# uint64 `inside [0..19]` left bins 13-15 unhit over 400 draws), so a SAT model
# is drawn through the uniform sampler rather than read back. Its old opt-outs,
# VSC_DVSOLVE_BVSAT=0 and VSC_DVSOLVE_BVSAT_SERVE_SAT=0, deferred to Boolector
# and went with the fallback (v2 plan V24).

# When BV-SAT serves SAT, route the model through the XOR/parity-hashing uniform
# sampler (bvsat_sampler) instead of reading back kissat's clustered model. This
# is what makes BV-SAT's models usable for stimulus (see bvsat_sampler.py). On
# by default; set VSC_DVSOLVE_BVSAT_SAMPLER=0 to A/B against the raw clustered
# readback.
_BVSAT_SAMPLER = os.environ.get("VSC_DVSOLVE_BVSAT_SAMPLER", "1") != "0"

# Attribute under which a RandSet's compiled plan is cached on its anchor field.
_PLAN_ATTR = "_dvsolve_plan"
# The signature of the last problem an anchor compiled without keeping it: a
# plan is retained only when the same anchor compiles the same problem twice.
_SEEN_ATTR = "_dvsolve_seen"

# Retained plans are bounded process-wide (least recently used evicted first)
# by the native memory they hold: each keeps a compiled SolveCtx, 64 KiB and up.
# Without a bound, a program that keeps many randomized objects alive (riscv-dv
# keeps every generated instruction) keeps every one's context: ~500 KB per
# instruction. VSC_DVSOLVE_PLAN_CACHE_MB sets the budget; 0 retains nothing.
_PLAN_CACHE_BYTES = int(float(os.environ.get("VSC_DVSOLVE_PLAN_CACHE_MB", "64")) * (1 << 20))


class _PlanCache(object):
    """LRU bookkeeping for the plans retained on anchor fields.

    A plan still lives on its owner (an anchor field for a per-RandSet plan,
    the randomizer's _RandPlan for a merged one), so its lifetime is never
    longer than its object's and a lookup stays one getattr; this only tracks
    the retained set and evicts from it. Entries hold weak references, so an
    object's garbage collection frees its plan as before."""

    def __init__(self, budget):
        import collections
        self.budget = budget
        self.bytes = 0
        self._lru = collections.OrderedDict()     # id(plan) -> (weakref plan, weakref anchor)
        self.evictions = 0

    def add(self, owner, attr, plan):
        """Track `plan`, held as `owner.<attr>`; False if it alone exceeds the
        budget (the caller then doesn't keep it). Evicting a plan clears the
        attribute and frees the native context."""
        import weakref
        if plan.nbytes > self.budget:
            return False
        plan.cached = True
        self._lru[id(plan)] = (weakref.ref(plan), weakref.ref(owner), attr)
        self.bytes += plan.nbytes
        self._trim()
        return True

    def set_budget(self, nbytes):
        """Change the budget, evicting at once down to it."""
        self.budget = int(nbytes)
        self._trim()

    def _trim(self):
        while self.bytes > self.budget and self._lru:
            _, (pr, orf, at) = self._lru.popitem(last=False)
            p = pr()
            if p is None:
                continue
            self.bytes -= p.nbytes
            p.cached = False
            o = orf()
            if o is not None and getattr(o, at, None) is p:
                setattr(o, at, None)
            p.destroy()
            self.evictions += 1

    def touch(self, plan):
        k = id(plan)
        if k in self._lru:
            self._lru.move_to_end(k)

    def forget(self, plan):
        if self._lru.pop(id(plan), None) is not None:
            self.bytes -= plan.nbytes

    def stats(self):
        return {"plans": len(self._lru), "bytes": self.bytes, "budget": self.budget,
                "evictions": self.evictions}


_PLAN_CACHE = _PlanCache(_PLAN_CACHE_BYTES)


def plan_cache_stats():
    """Retained compiled plans: count, bytes held, budget, evictions so far."""
    return _PLAN_CACHE.stats()


def set_plan_cache_budget(nbytes):
    """Bound the native memory retained compiled plans may hold (bytes; 0 keeps
    none). Takes effect at once. The default is VSC_DVSOLVE_PLAN_CACHE_MB (64)."""
    _PLAN_CACHE.set_budget(nbytes)


def _guard_references_rand(cond_l):
    """True iff any field referenced by the guard expressions in ``cond_l`` is a
    rand field — i.e. the guard's truth is NOT a solve-time constant. Used to
    decide whether a conditional dist's active branch can be resolved now."""
    from vsc.model.model_visitor import ModelVisitor

    class _Probe(ModelVisitor):
        def __init__(self):
            super().__init__()
            self.has_rand = False

        def visit_expr_fieldref(self, e):
            if getattr(e.fm, "is_used_rand", False):
                self.has_rand = True

    p = _Probe()
    for cond in cond_l:
        cond.accept(p)
    return p.has_rand


def _guard_field_vids(cond_l, idmap):
    """Var ids of the *rand* fields referenced by the guard expressions in
    ``cond_l`` (those that must be frozen before a conditional dist's branch is
    selectable). Only fields present in ``idmap`` are returned; a guard over a
    field outside this RandSet's id map can't be staged here."""
    from vsc.model.model_visitor import ModelVisitor

    vids = set()

    class _Collect(ModelVisitor):
        def visit_expr_fieldref(self, e):
            if getattr(e.fm, "is_used_rand", False) and idmap.has(e.fm):
                vids.add(idmap.id_of(e.fm))

    c = _Collect()
    for cond in cond_l:
        cond.accept(c)
    return vids


class _BulkReadback(object):
    """Pre-built buffers for reading a fixed list of solved vars back in one
    FFI call (``solver_get_values``) instead of one call per field.

    Built once for a given ``[(field, var_id, width, signed)]`` list and reused
    for the life of the compiled ctx, so nothing is allocated per solve. The
    per-element ``ctx.get_value`` loop was 28.8% of a warm 128-element
    randomize(); this is the same work in one boundary crossing.

    Only valid for variables that fit in an int64 — both call sites already
    route >64-bit fields to the BV-SAT path before reaching a readback.
    """

    __slots__ = ("n", "ids", "out", "_mv", "fields", "masks", "uniform_mask")

    def __init__(self, entries):
        import ctypes
        n = len(entries)
        self.n = n
        self.ids = (ctypes.c_uint32 * n)(*[e[1] for e in entries])
        self.out = (ctypes.c_int64 * n)()
        # memoryview().cast('B').cast('q').tolist() is the Python-int
        # materialisation floor (measured 0.267us vs 0.281us for the ideal;
        # list(buf) is 14x worse). The via-'B' step is required: casting a
        # c_int64 array directly to 'q' raises
        # "NotImplementedError: memoryview: unsupported format <q".
        self._mv = memoryview(self.out).cast('B').cast('q')
        self.fields = [e[0] for e in entries]
        # `_as_field_value` masks unsigned fields to width and leaves signed
        # fields alone. Precompute the mask per entry rather than recomputing
        # (1 << width) - 1 per element per solve; None means "no work".
        self.masks = [None if e[3] else (1 << e[2]) - 1 for e in entries]
        # The overwhelmingly common case (an array of one unsigned type) is a
        # single mask for every entry, which lets the hot loop drop a zip leg.
        first = self.masks[0] if n else None
        self.uniform_mask = first if all(m == first for m in self.masks) else False

    def read_into_fields(self, ctx):
        """One FFI call, then write every value into its field."""
        ctx.get_values(self.ids, self.out, self.n)
        vals = self._mv.tolist()
        m = self.uniform_mask
        if m is False:
            for f, v, fm in zip(self.fields, vals, self.masks):
                f.set_val(v if fm is None else v & fm)
        elif m is None:
            for f, v in zip(self.fields, vals):
                f.set_val(v)
        else:
            for f, v in zip(self.fields, vals):
                f.set_val(v & m)


class _CompiledPlan(object):
    """A built+compiled dv-solve problem retained for reuse.

    Holds the native resources (builder buffer + SolveCtx) alive and the data
    needed to (a) decide whether it is still valid for a later RandSet and
    (b) read solved values back. Reuse = ``ctx.reset()`` + ``ctx.solve(seed)``
    instead of rebuilding and recompiling from scratch.
    """

    __slots__ = ("ctx", "readback", "struct_sig", "const_fields", "_keepalive",
                 "bulk", "nbytes", "cached", "sample_vars", "__weakref__")

    def __init__(self, ctx, readback, struct_sig, const_fields, keepalive,
                 sample_vars=None):
        # sample_vars set: `ctx` is an incremental BV-SAT context that serves by
        # drawing again (bvsat_sampler.draw_native), not a SolveCtx (V19).
        self.sample_vars = sample_vars
        # Native memory this plan keeps alive: the context's working buffer and
        # the problem buffer (the block allocator's growth isn't visible here).
        self.nbytes = (_bvsat_nbytes(ctx) if sample_vars is not None
                       else _ctx_nbytes(ctx))
        self.cached = False
        # Lazily-built _BulkReadback for `readback` (S1.2). Built on the first
        # reuse rather than here, so a plan that is never reused pays nothing.
        self.bulk = None
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
        if self.cached:
            self.cached = False
            _PLAN_CACHE.forget(self)
        ctx = self.ctx
        self.ctx = None
        if ctx is not None:
            try:
                ctx.destroy()
            except Exception:
                pass

    def __del__(self):
        self.destroy()

    # A copied model object gets no plan: the native context can't be copied
    # (ctypes pointers), and the copy's fields aren't the ones it reads back.
    # Its first randomize() compiles its own. (riscv-dv deep-copies randomized
    # instruction streams.)
    def __copy__(self):
        return None

    def __deepcopy__(self, memo):
        return None


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


# Post-solve model validation (KF-1b). dv-solve's `validate_model()` re-evaluates
# every constraint in the problem against the assignment the search produced, and
# returns the violation count. It is the net for the class of bug where a
# constraint is *mis*-compiled — the search then satisfies only what it was given
# and reports SOLVE_OK on a model that violates the user's constraints, silently.
#
# That is not hypothetical: KF-1 (`if (a<b) c<d; else c==d` with mismatched
# operand widths) returned violating models 63% of the time and nothing in the
# normal flow noticed. Only the XCHECK differential run — which needs Boolector
# and is off by default — caught it. `validate_model` catches the same thing with
# no oracle, so it can run anywhere.
#
# Off by default (it re-walks the constraint tree per solve). Set
# VSC_DVSOLVE_VALIDATE=1 to raise on a violation; CI runs with it on.
# Constructs the C evaluator cannot handle (arrays, sums, countones, clog2,
# in_set, in_range) are skipped, so a clean run is not a proof of correctness.
_VALIDATE_ENABLED = os.environ.get("VSC_DVSOLVE_VALIDATE", "0") != "0"


class ModelValidationError(Exception):
    """A dv-solve SOLVE_OK model failed post-solve constraint re-evaluation."""


def _validate_model(ctx, where):
    """Re-check a just-solved model against its own problem. Raises on violation.

    Never masks a solve: a validator that itself errors (an older dv-solve with no
    `solver_validate_model`) is reported as unavailable, not as a violation."""
    if not _VALIDATE_ENABLED:
        return
    try:
        n = ctx.validate_model()
    except AttributeError:
        return
    if n:
        raise ModelValidationError(
            "dv-solve returned SOLVE_OK on a model violating %d constraint(s) "
            "(%s) — a mis-compiled constraint. See doc/notes/known_failures.md "
            "KF-1." % (n, where))


def _oracle_label(fields):
    """Names a context in the dv-solve oracle's records (vsc.set_solver_oracle):
    the fields it randomizes. Built only while an oracle is on."""
    from dv_solve.oracle import get_default_oracle
    if get_default_oracle() is None:
        return None
    names = []
    for f in fields:
        try:
            names.append(f.fullname)
        except Exception:
            names.append(getattr(f, "name", "?"))
    return " ".join(names[:16]) + (" ..." if len(names) > 16 else "")


class _MergedPlan(object):
    """The whole-problem merged solve's compiled context, cached on the
    randomizer's _RandPlan.merged (see DvSolveBackend.solve_merged)."""

    __slots__ = ("ctx", "readback", "bulk", "nbytes", "cached", "__weakref__")

    def __init__(self, ctx, readback):
        self.ctx = ctx
        self.readback = readback
        self.bulk = None            # _BulkReadback, built on first readback (S1.2)
        self.nbytes = _ctx_nbytes(ctx)
        self.cached = False

    def destroy(self):
        if self.cached:
            self.cached = False
            _PLAN_CACHE.forget(self)
        ctx, self.ctx = self.ctx, None
        if ctx is not None:
            try:
                ctx.destroy()
            except Exception:
                pass

    def __del__(self):
        self.destroy()

    def __copy__(self):
        return None

    def __deepcopy__(self, memo):
        return None


def _ctx_nbytes(ctx):
    import ctypes
    n = 0
    for attr in ("_ctx_buf", "_problem"):
        b = getattr(ctx, attr, None)
        try:
            n += ctypes.sizeof(b)
        except TypeError:
            n += len(getattr(b, "raw", b"") or b"") if b is not None else 0
    return n


# Smallest encoded problem (AIG gates) worth keeping between randomize() calls
# for the BV-SAT sampler; see retain() in _build_and_solve.
_BVSAT_KEEP_MIN_ANDS = 20000


def _bvsat_nbytes(bb):
    """Native memory an incremental BV-SAT context holds, roughly: the AIG and
    the SAT solver's clauses and variables, plus the problem buffer."""
    import ctypes
    st = bb.stats()
    n = 16 * st["aig_ands"] + 32 * st["sat_clauses"] + 64 * st["sat_vars"]
    try:
        n += ctypes.sizeof(bb._problem)
    except TypeError:
        pass
    return n


def _fit_weights_u32(entries):
    """Scale ``add_dist`` weights by one common factor so the largest fits the
    native uint32 weight, keeping their ratios. Each entry's mass is
    ``weight`` (or ``weight * count`` for ``:=``), so a common factor keeps
    every mass ratio too. Rounding: a nonzero weight stays at least 1 (so it
    is never turned into a zero-weight exclusion); otherwise the relative
    error of a weight w' after scaling is at most 1/(2 w'). Entries that
    already fit are returned unchanged."""
    wmax = max((e["weight"] for e in entries), default=0)
    if wmax <= _U32_MAX:
        return entries
    out = []
    for e in entries:
        w = e["weight"]
        if w:
            w = max(1, (w * _U32_MAX + wmax // 2) // wmax)
        out.append({**e, "weight": w})
    return out


_U32_MAX = (1 << 32) - 1


def _dist_mass(entries):
    """Total selection mass of an ``add_dist`` entry list: ``weight`` per
    ``:/`` entry, ``weight * count`` per ``:=`` entry."""
    return sum(e["weight"] * ((e["hi"] - e["lo"] + 1) if e["is_per_value"] else 1)
               for e in entries)


def _guard_ref(tr, c):
    """A dist scope's guard expression as a boolean ref, read logically as
    ``_guard_holds`` reads it: an if/else false branch's ``Not(..)`` wrapper
    is a logical not of its operand's truth."""
    from vsc.model.expr_unary_model import ExprUnaryModel
    from vsc.model.unary_expr_type import UnaryExprType
    from dv_solve.problem import UN_NOT
    if isinstance(c, ExprUnaryModel) and c.op == UnaryExprType.Not:
        return tr._b.expr_unary(UN_NOT, _guard_ref(tr, c.expr))
    return tr._translate_guarded_cond(c)


def _mix_dist_entries(per):
    """One entry list whose distribution is the equal-probability mixture of
    the dists in ``per``: dist i's weights are multiplied by the product of the
    other dists' total masses, so every dist ends with the same total mass.
    Zero-weight entries are dropped (the caller excludes them as hard
    constraints), as is a dist with no mass at all. Exact, then fitted to
    uint32 by a common factor."""
    per = [[e for e in ents if e["weight"]] for ents in per]
    per = [ents for ents in per if ents]
    masses = [_dist_mass(ents) for ents in per]
    out = []
    for i, ents in enumerate(per):
        k = 1
        for j, m in enumerate(masses):
            if j != i:
                k *= m
        out.extend({**e, "weight": e["weight"] * k} for e in ents)
    return _fit_weights_u32(out)


def _sample_domain(f, lo, hi, bound_m):
    """The domain the BV-SAT samplers draw a value of ``f`` from: the
    ``add_var`` bounds ``lo``/``hi`` for a field of <= 64 bits. Those bounds
    are int64, so a wider field's are clamped to the int64 envelope (see
    ``_domain_of``); its domain is instead the field's natural range cut to
    the bound visitor's enclosing range, or a solve-order or ``dist`` pin
    could only take an int64 value."""
    if f.width <= 64:
        return lo, hi
    if f.is_signed:
        lo, hi = -(1 << (f.width - 1)), (1 << (f.width - 1)) - 1
    else:
        lo, hi = 0, (1 << f.width) - 1
    bound = bound_m.get(f) if bound_m is not None else None
    range_l = bound.domain.range_l if bound is not None else None
    if range_l:
        blo = max(lo, min(r[0] for r in range_l))
        bhi = min(hi, max(r[1] for r in range_l))
        if blo <= bhi:
            lo, hi = blo, bhi
    return lo, hi


def _dist_patterns(f, entries):
    """``add_dist`` entries for field ``f`` as the engine takes them: int64
    bounds. An unsigned 64-bit field's values above INT64_MAX become their
    two's-complement bit patterns, which the engine orders unsigned for such
    a var. The natural (Python int) entries are what the BV-SAT samplers
    draw from, so only the native call is converted."""
    if f.is_signed or f.width != 64:
        return entries
    if all(e["hi"] < (1 << 63) for e in entries):
        return entries
    def pat(v):
        return v - (1 << 64) if v >= (1 << 63) else v
    return [{**e, "lo": pat(e["lo"]), "hi": pat(e["hi"])} for e in entries]


def _native_dist(b, vid, f, entries):
    """Give ``entries`` to the engine's value picker (``add_dist``). Its
    bounds are int64, so a field over 64 bits gets none: such a RandSet is
    always served by BV-SAT, whose samplers take the weighting from the
    captured entries (``sample_dist``, ``sample_dist_conditional``), V15."""
    if f.width <= 64:
        b.add_dist(vid, _dist_patterns(f, entries))


def _make_solve_ctx(buf, problem_sz=0, label=None):
    """Create a SolveCtx. A dynamic-pool dv-solve sizes itself; on an older
    fixed-pool one, a generic compile failure (likely pool overflow) is retried
    with a problem-sized buffer, growing 4x up to ``_CTX_BUF_MAX``, then
    propagates. Compile *verdicts* (UNSAT / incomplete) are real and not
    retried. ``label`` names the context in the oracle check's records."""
    from dv_solve.ctx import (
        SolveCtx, CompileUnsatError, CompileIncompleteError)
    kw = {"label": label} if label is not None else {}
    # A dv-solve with the dynamic pool grows the context itself (and ignores
    # ctx_buf_size), so try that first. Only an older, fixed-pool dv-solve
    # fails here on a large problem and needs the sized retries below.
    try:
        return SolveCtx(buf, **kw)
    except (CompileUnsatError, CompileIncompleteError):
        raise
    except RuntimeError as e:
        last = e
    # First estimate from the problem, rounded up to a 64 KiB multiple, and
    # capped so a large problem still gets an attempt at _CTX_BUF_MAX.
    size = min(_CTX_BUF_MAX,
               max(_CTX_BUF_FLOOR,
                   (problem_sz * _CTX_BUF_PER_PROBLEM_BYTE + 0xFFFF) & ~0xFFFF))
    while size <= _CTX_BUF_MAX:
        try:
            return SolveCtx(buf, ctx_buf_size=size, **kw)
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
    one native ``add_dist`` (weighted, per-value/per-range) on the distributed
    var, layered on top of the hard ``inside`` membership that the upstream
    ``DistConstraintBuilder`` expansion already emits (which doubles as the
    BV-SAT "Domain-Twin" so the completeness engine stays sound), with each
    zero-weight entry excluded as a hard constraint. Several dists on one field
    are their mixture; a rand-guarded dist is staged by the BV-SAT samplers,
    which also serve every dist on a field over 64 bits from the same entries
    (``_add_dist_for_field``)."""

    name = "dv-solve"
    supports_soft = True
    supports_dist_native = True
    randomizes_internally = True

    # Stage 1 (declared-only bounds), Option A — DEFAULT ON, kill-switch
    # VSC_DVSOLVE_DECLARED_ONLY=0. The Randomizer's post-expansion bound pass runs
    # in `declared_only` mode: narrow-field (<=32-bit) range-inequality
    # propagation is skipped (the native core re-derives those bounds and its
    # narrow-field sampler is uniform regardless of declared-domain width),
    # trimming ~20% of cold-path time on large array problems. Correctness/
    # distribution carriers are KEPT — `==` pins, `inside`/rangelist folds, and
    # WIDE-field (>32-bit) range propagators (the wide sampler needs the tight
    # domain to avoid boundary bias). A blanket "skip all propagation" variant was
    # validated and REJECTED (regressed wide `==`, rangelist folds, and wide
    # fairness). Full ve/unit + ve/unit_dc pass with this ON. Not bit-identical:
    # per-seed values change for narrow-array/wide problems (still valid/uniform).
    # See doc/notes/dv_solve_native_full_problem_plan.md (Stage 1 / Option A).
    derives_bounds = os.environ.get("VSC_DVSOLVE_DECLARED_ONLY", "1") != "0"

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

        # An empty rand set has no variable to solve for, but it may still carry
        # a hard constraint over only non-rand (or rand_mode-disabled) fields —
        # e.g. a disabled field whose fixed value violates its own constraint.
        # Such a constant-false constraint is UNSAT (Boolector reports it; the
        # dv-solve builder drops variable-free constraints, so validate here).
        if len(rand_fields) == 0:
            _check_const_constraints(rs)
            return SolveResult(status=0)

        # Distribution (`dist`) is handled natively: _populate_builder emits a
        # native add_dist for each distributed field (see _dist_entries). The
        # un-encodable shapes (§5 of the Phase-B plan) raise BackendIncomplete
        # from there and defer per-RandSet, rather than deferring every dist.

        # Field width vs the engines:
        #  - <=64 bits: the primary bounds-propagation engine (64-bit) handles it
        #    — the optimized common path, unchanged.
        #  - 65.._MAX_FIELD_WIDTH bits: the primary engine can't represent
        #    it, but the width-agnostic BV-SAT engine can (Phase D).
        #  - wider: past the engine's ceiling (DVS_MAX_WIDTH) — the whole
        #    RandSet is unsupported.
        # A RandSet with any wide field is routed straight to BV-SAT serving
        # (there is no 64-bit primary path for it); see _build_and_solve.
        for f in rand_fields:
            if f.width > _MAX_FIELD_WIDTH:
                raise BackendIncomplete(
                    "dv-solve: field '%s' width %d exceeds %d bits" % (
                        getattr(f, "name", "?"), f.width, _MAX_FIELD_WIDTH),
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
                if (plan.sample_vars is not None and plan.struct_sig == sig
                        and plan.values_unchanged()):
                    # A BV-SAT-served RandSet: draw again from the encoded
                    # instance. Anything but SAT rebuilds, below, which gives
                    # the authoritative verdict.
                    from vsc.model.solver import bvsat_sampler
                    from dv_solve.bvsat import BVSAT_SAT
                    _PLAN_CACHE.touch(plan)
                    rc = bvsat_sampler.draw_native(
                        plan.ctx, plan.readback, plan.sample_vars,
                        randstate.randint(0, (1 << 63) - 1), solve_info=solve_info)
                    if rc == BVSAT_SAT:
                        if plan.ctx.sample_stale():
                            # Earlier draws' planes now outweigh the problem
                            # and slow every solve: drop the instance; the
                            # next randomize() encodes a fresh one.
                            setattr(anchor, _PLAN_ATTR, None)
                            plan.destroy()
                        return SolveResult(status=0)
                elif plan.struct_sig == sig and plan.values_unchanged():
                    _PLAN_CACHE.touch(plan)
                    plan.ctx.reset()
                    # The cached SolveCtx keeps its own problem buffer
                    # (SolveCtx._problem); pass it so a non-OK re-solve can fall
                    # back to the BV-SAT engine like the build path.
                    self._solve_and_readback(
                        plan.ctx, plan.readback, randstate, solve_info,
                        problem_buf=getattr(plan.ctx, "_problem", None),
                        has_order=has_order, rand_order_l=rand_order_l,
                        n_softs=len(rs.soft_constraints()),
                        plan=plan)
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
        near_unsat = False
        for f in rand_fields:
            vid = idmap.add(f)
            dom = self._domain_of(f, bound_m)
            if dom is None:
                # ``_domain_of`` emptied the field's enclosing range at width <= 64
                # (the width>64 wide case instead returns a *free* range and routes
                # to BV-SAT). The constraint-narrowed domain is empty at this width
                # — e.g. ``a == 500`` on a uint8 — a near-unsat the primary's
                # bound-tightening cannot soundly *declare*. Rather than defer the
                # verdict to Boolector (the old ``unsat-defer``), declare the var
                # free across its width and route the whole RandSet to the complete
                # internal BV-SAT engine, which IS the UNSAT authority (Phase A): it
                # decides SAT/UNSAT itself (and serves a value if the empty bound
                # was a spurious tightening). The original constraints still narrow
                # the var inside BV-SAT, so this never "solves" an impossible value
                # — the over-wide literal stays full-width (translator literal
                # sizing) and the equality is UNSAT exactly as Boolector reports.
                if f.is_signed:
                    lo, hi = -(1 << (f.width - 1)), (1 << (f.width - 1)) - 1
                else:
                    lo, hi = 0, (1 << f.width) - 1
                b.add_var(vid, f.width, bool(f.is_signed), lo, hi)
                sample_vars.append((vid, int(f.width), lo, hi, bool(f.is_signed)))
                near_unsat = True
                continue
            lo, hi, gap_ranges = dom
            b.add_var(vid, f.width, bool(f.is_signed), lo, hi)
            sample_vars.append((vid, int(f.width), *_sample_domain(f, lo, hi, bound_m),
                                bool(f.is_signed)))
            if gap_ranges is not None:
                gapped.append((f, gap_ranges))

        # 1b. A solve order (`solve a before b`): rand_order_l lists its stages,
        # earliest first. The engine decides them in that order; fields in no
        # stage come last, uniform over the solutions the stages leave.
        for stage, grp in enumerate(getattr(rs, "rand_order_l", None) or (), 1):
            for f in grp:
                if idmap.has(f):
                    b.set_var_order(idmap.id_of(f), min(stage, 255))

        tr = DvSolveExprTranslator(b, idmap)
        if near_unsat:
            # A field's domain emptied at its width: the primary can neither serve
            # nor authoritatively reject this RandSet, so force the complete BV-SAT
            # engine (UNSAT authority + width-agnostic serving).
            tr.requires_bvsat = True

        # Fields carrying a native `dist`: their weighted add_dist (step 4 below)
        # owns the value picker, so the gap-range *uniform* add_dist must be
        # skipped for them — two add_dist calls on one var would collide (the
        # weighted one is what we want). Their hard membership still comes from
        # the dist's `inside` (in_c) via the normal constraint loop.
        dist_field_m = getattr(rs, "dist_field_m", None) or {}
        dist_fields = set(f for f in dist_field_m if idmap.has(f))
        # The native EXPR_IN_RANGES membership shortcut must not fire for dist
        # fields (their membership is owned by the dist encoding).
        tr.dist_fields = dist_fields

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
            membership = self._membership_expr(f, gap_ranges)
            # Prefer the native multi-range membership propagator (G-2); fall
            # back to the OR encoding for shapes it can't take (which then route
            # to BV-SAT as before).
            mref = tr.try_native_in_ranges(membership)
            if mref is None:
                mref = tr.translate(membership)
            b.add_constraint(mref)
            b.add_dist(idmap.id_of(f), [
                {"lo": r[0], "hi": r[1], "weight": 1, "is_per_value": True}
                for r in gap_ranges])

        # 1c. Native dist weighting. The hard `inside` membership twin is
        #     already emitted by the normal constraint loop (DistConstraintBuilder
        #     expansion), satisfying the BV-SAT Domain-Twin Invariant; here we
        #     add only the weighted selection the swizzler would otherwise
        #     supply. Un-encodable shapes raise BackendIncomplete (deferral).
        # vid -> weighted DistEntry list, captured so the BV-SAT serving path
        # (sample_dist) can honor the same weighting the primary's add_dist
        # applies, for a dist-bearing RandSet that force-serves via BV-SAT.
        tr.dist_targets = {}
        # Rand-guarded conditional dist: {vid: [(cond_l, entries), ...]} plus the
        # union of guard var-ids to freeze first. Presence forces BV-SAT serving so
        # the guard-staged sampler applies the active branch's weighting (else the
        # weighting would collapse to the uniform union — the old §5 behavior).
        tr.cond_dist_targets = {}
        tr.dist_guard_vids = set()
        for f in dist_fields:
            scopes = dist_field_m[f]
            entries, cond_target = self._add_dist_for_field(
                b, idmap, f, scopes, tr)
            if entries:
                tr.dist_targets[idmap.id_of(f)] = entries
            if cond_target is not None:
                tr.cond_dist_targets[idmap.id_of(f)] = cond_target["branches"]
                tr.dist_guard_vids |= cond_target["guard_vids"]
        if tr.cond_dist_targets:
            tr.requires_bvsat = True

        # Soft serving posture (soft-constraints engine plan, DSE-0/DSE-2). The
        # dv-solve *primary* engine honors softs correctly — including *guarded*
        # (conditional) softs, which lower to the disjunction soft `(!cond)||expr`:
        # the relaxation loop keeps the maximal priority-respecting soft set and
        # bound-propagation enforces a kept disjunction (verified natively, DSE-0;
        # the earlier "0/20" was a pyvsc translator memo-key bug, since fixed —
        # see dvsolve_translator.translate). So a primary-served soft RandSet needs
        # NO gate here. The *BV-SAT serve path* was historically soft-less (a
        # soft-bearing RandSet that force-serves via requires_bvsat / wide, or falls
        # to BV-SAT on primary-incomplete, dropped its softs silently). DSE-2 closed
        # that: `_solve_via_bvsat` now runs the engine's soft-aware MaxSAT
        # (`maxsat_keepset` -> `zsp_bbsolver_check_maxsat`) to fix the maximal
        # priority-respecting kept-soft set and enforces it as hard on every sampler
        # draw, so both guarded and unconditional softs are honored natively on the
        # serve path too. No soft RandSet is deferred or silently dropped here.

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
                # translate_soft materializes the soft's expr (a bare soft, or the
                # guarded `(!cond)||soft` of a priority-bearing implies); the engine
                # owns the relaxation via add_soft_constraint. A soft translated in
                # the *hard* tree drops to nothing (see visit_constraint_soft).
                b.add_soft_constraint(tr.translate_soft(softs[i]), dv_pri)

        return tr, sample_vars

    def _build_and_solve(self, rs, rand_fields, bound_m, randstate,
                         solve_info, anchor, sig, has_order=False,
                         has_wide=False, rand_order_l=None) -> SolveResult:
        from dv_solve.builder import SolveProblemBuilder
        from dv_solve.ctx import (
            SolveCtx, CompileUnsatError, CompileIncompleteError,
        )
        from vsc.model.solver.var_id_map import VarIdMap

        # A hard constraint that is fully constant and false makes this RandSet
        # unsatisfiable regardless of the rand fields (the builder would silently
        # drop it — it has no variable). Only checked on the build path: a reused
        # compiled plan already passed this at build time and is served only while
        # its referenced constant values are unchanged (values_unchanged()).
        _check_const_constraints(rs)

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
            n_softs = len(rs.soft_constraints())

            # A RandSet the primary engine cannot solve soundly goes straight
            # to the complete BV-SAT engine:
            #  - a >64-bit field has no 64-bit primary path at all (Phase D);
            #  - an aux-lifted logical-combination implication guard makes the
            #    primary's disjunction propagation unsound (F-E3), but the emitted
            #    encoding is correct and BV-SAT is complete (Phase F / F-2).
            # The <=64-bit, primary-sound common path below is unchanged.
            if has_wide or tr.requires_bvsat:
                def retain(bb, _sv=sample_vars, _rb=readback, _tr=tr, _rs=rs):
                    # Keep the encoded BV-SAT instance for the next randomize(),
                    # admitted as a compiled plan is (the second time this
                    # anchor builds this problem). Only a big one: a reused
                    # instance carries earlier draws' planes and learned
                    # clauses, which costs more than encoding a small problem
                    # again (measured: a 64-bit `a == b` draws in 33 ms fresh,
                    # 60-90 ms reused; a 65536-bit `a < b` in 25 ms reused).
                    if anchor is None or sig is None:
                        return False
                    if bb.stats()["aig_ands"] < _BVSAT_KEEP_MIN_ANDS:
                        return False
                    if getattr(anchor, _SEEN_ATTR, None) != sig:
                        setattr(anchor, _SEEN_ATTR, sig)
                        return False
                    keepalive = (list(_rs.constraints()), list(_rs.soft_constraints()))
                    plan = _CompiledPlan(bb, _rb, sig, list(_tr.const_fields.items()),
                                         keepalive, sample_vars=_sv)
                    if _PLAN_CACHE.add(anchor, _PLAN_ATTR, plan):
                        setattr(anchor, _PLAN_ATTR, plan)
                        return True
                    plan.ctx = None
                    return False
                return self._solve_via_bvsat(
                    buf, readback, randstate, solve_info,
                    make_base=make_base, sample_vars=sample_vars,
                    has_order=has_order,
                    rand_order_l=rand_order_l, dist_targets=tr.dist_targets,
                    cond_dist_targets=tr.cond_dist_targets,
                    dist_guard_vids=tr.dist_guard_vids, n_softs=n_softs,
                    retain=retain)

            try:
                ctx = _make_solve_ctx(buf, problem_sz,
                                      label=_oracle_label(rand_fields))
            except (CompileUnsatError, CompileIncompleteError, RuntimeError):
                # Primary can't compile / proves a non-trusted UNSAT -> let the
                # BV-SAT engine decide authoritatively on the same buffer.
                return self._solve_via_bvsat(
                    buf, readback, randstate, solve_info,
                    make_base=make_base, sample_vars=sample_vars,
                    has_order=has_order, rand_order_l=rand_order_l,
                    dist_targets=tr.dist_targets,
                    cond_dist_targets=tr.cond_dist_targets,
                    dist_guard_vids=tr.dist_guard_vids, n_softs=n_softs)

            solved_by_primary = self._solve_and_readback(
                ctx, readback, randstate, solve_info, problem_buf=buf,
                make_base=make_base, sample_vars=sample_vars,
                has_order=has_order, rand_order_l=rand_order_l,
                dist_targets=tr.dist_targets,
                cond_dist_targets=tr.cond_dist_targets,
                dist_guard_vids=tr.dist_guard_vids, n_softs=n_softs)

            # Retain the compiled ctx for reuse only when the *primary* engine
            # produced the solution — a ctx that needed the BV-SAT fallback is
            # not reusable (it re-solves to the same non-OK result). The plan owns
            # `ctx` (which keeps its own problem buffer alive); it is freed when
            # the plan is evicted (signature change) or its anchor field is
            # garbage-collected.
            # Admission: keep the plan only when this anchor already compiled
            # this same problem once. An object randomized once, or a RandSet
            # rebuilt every call (randomize_with's inline constraints are new
            # objects each time, so the signature never repeats), would hold a
            # context that can never be reused. A repeated randomize() pays one
            # extra compile, then reuses.
            if solved_by_primary and anchor is not None and sig is not None:
                if getattr(anchor, _SEEN_ATTR, None) != sig:
                    setattr(anchor, _SEEN_ATTR, sig)
                else:
                    # Keep the constraint objects whose ids are in `sig` alive so
                    # Python can't recycle a freed id into the next RandSet and
                    # cause a false signature match (see _CompiledPlan._keepalive).
                    keepalive = (list(rs.constraints()), list(rs.soft_constraints()))
                    plan = _CompiledPlan(
                        ctx, readback, sig, list(tr.const_fields.items()), keepalive)
                    if _PLAN_CACHE.add(anchor, _PLAN_ATTR, plan):
                        setattr(anchor, _PLAN_ATTR, plan)
                        cached = True
                    else:
                        plan.ctx = None      # the finally below frees ctx

            return SolveResult(status=0)
        finally:
            # The builder is transient — finalize() produced a self-contained,
            # Python-owned buffer, so the builder is never needed past this call.
            b.destroy()
            if not cached and ctx is not None:
                # Build/compile/solve failed (or caching disabled): free the ctx.
                ctx.destroy()

    # ------------------------------------------------------------------ #
    # Whole-problem merged solve (independent partitions in one native call) #
    # ------------------------------------------------------------------ #

    def solve_merged(self, randsets, bound_m, randstate, plan) -> bool:
        """Solve every RandSet of a plan-cached problem in ONE native problem.

        RandInfoBuilder emits *independent* partitions, so the union is a
        block-diagonal problem: one compiled ctx, one ``solve(fair_pick)`` and one
        readback replace the per-RandSet loop (~9x on a 128-partition warm solve —
        the per-RandSet reuse-signature/dispatch/dispose overhead dominates once
        the problem is plan-cached). The compiled ctx is cached on ``plan.merged``
        and reused (reset + solve) until the plan is evicted.

        Returns True on success (values written into the fields). Returns False
        when the problem is not mergeable (a special RandSet — dist / rand_order /
        soft / >64-bit / near-unsat) or a merged solve did not cleanly succeed, so
        the caller falls back to the authoritative per-RandSet path (which also
        gives UNSAT attribution). Never returns a wrong answer: a non-OK merged
        solve defers rather than guessing."""
        from dv_solve.ctx import SOLVE_OK
        from vsc.model.solver import xcheck

        # XCHECK differential verification hooks the per-RandSet solve; the merged
        # fast path would bypass it. In that verification mode, defer to the
        # per-RandSet path so every model is still cross-checked (perf irrelevant).
        if xcheck.is_enabled():
            return False

        merged = plan.merged
        if merged is False:
            return False                       # known non-mergeable
        if merged is None:
            merged = self._build_merged(randsets, bound_m)
            if merged is False:
                plan.merged = False
                return False
            # Built on first use (the merged solve is also the faster cold
            # path), retained within the plan-cache budget; an evicted plan is
            # rebuilt here on its next use.
            if _PLAN_CACHE.add(plan, "merged", merged):
                plan.merged = merged
        else:
            _PLAN_CACHE.touch(merged)
        ctx, readback = merged.ctx, merged.readback

        _t = PT.now()
        ctx.reset()
        seed = randstate.randint(0, (1 << 63) - 1)
        rc = ctx.solve(seed=seed, fair_pick=True)
        PT.add("solve", _t)
        if rc != SOLVE_OK:
            # Not an authoritative UNSAT proof (the primary search is incomplete on
            # some shapes) — defer to the per-RandSet path, which routes to the
            # complete BV-SAT engine / external fallback and attributes the culprit.
            return False
        _validate_model(ctx, "merged solve")
        _t = PT.now()
        if opt_flags.BULK_READBACK:
            if merged.bulk is None:
                merged.bulk = _BulkReadback(readback)
            merged.bulk.read_into_fields(ctx)
        else:
            for f, vid, w, s in readback:
                f.set_val(self._as_field_value(ctx.get_value(vid), w, s))
        PT.add("readback", _t)
        return True

    def _build_merged(self, randsets, bound_m):
        """Compile all RandSets into one problem if every one is *plain* (≤64-bit,
        no dist / rand_order / soft / near-unsat) and the union is not too large.
        Returns ``(ctx, readback, bulk)`` or ``False`` (not mergeable — caller uses
        the per-RandSet path). ``bulk`` starts as None and is filled in by the
        first readback."""
        from dv_solve.builder import SolveProblemBuilder
        from dv_solve.ctx import CompileUnsatError, CompileIncompleteError
        from vsc.model.solver.var_id_map import VarIdMap

        # Fast plain-ness screen before touching native code, and count vars: the
        # merged native solve degrades super-linearly past a few hundred vars (a
        # single big problem loses to many tiny ones — a native scaling cliff
        # around ~256-384 vars), so cap the merge and let large problems keep the
        # per-RandSet path (which scales linearly). Tunable via env.
        n_vars = 0
        for rs in randsets:
            if rs.soft_constraints():
                return False
            if getattr(rs, "dist_field_m", None):
                return False
            if getattr(rs, "rand_order_l", None):
                return False
            for f in rs.rand_fields():
                if f.width > 64:
                    return False
                n_vars += 1
            # A constant-false hard constraint (over only non-rand fields) makes
            # this RandSet UNSAT; the merged builder drops variable-free
            # constraints, so it would "solve" an infeasible problem. Defer to the
            # per-RandSet path (which raises SolveFailure) — matching Boolector.
            try:
                _check_const_constraints(rs)
            except SolveFailure:
                return False
        if n_vars > _MERGE_MAX_VARS:
            return False

        b = SolveProblemBuilder()
        idmap = VarIdMap()
        readback = []
        ctx = None
        ok = False
        try:
            for rs in randsets:
                rf = rs.rand_fields()
                if not rf:
                    continue
                tr, _sv = self._populate_builder(b, idmap, rs, rf, bound_m)
                if tr.requires_bvsat or tr.dist_targets or tr.cond_dist_targets:
                    return False               # needs special serving; don't merge
                readback.extend(
                    (f, idmap.id_of(f), int(f.width), bool(f.is_signed))
                    for f in rf)
            if not readback:
                return False                   # nothing to merge
            buf, problem_sz = b.finalize()
            ctx = _make_solve_ctx(buf, problem_sz,
                                  label=_oracle_label(r[0] for r in readback))
            ok = True
            # bulk is built lazily on first readback (S1.2), so a merged plan
            # that is never actually solved costs nothing extra.
            return _MergedPlan(ctx, readback)
        except (CompileUnsatError, CompileIncompleteError, RuntimeError,
                BackendIncomplete):
            return False
        finally:
            b.destroy()
            if not ok and ctx is not None:
                ctx.destroy()

    def _solve_and_readback(self, ctx, readback, randstate, solve_info,
                            problem_buf=None, make_base=None,
                            sample_vars=None, has_order=False,
                            rand_order_l=None, dist_targets=None,
                            cond_dist_targets=None, dist_guard_vids=None,
                            n_softs=0, plan=None) -> bool:
        """Solve ``ctx`` with a fresh seed and write the solved values back into
        the fields. Shared by the build and reuse paths.

        Returns ``True`` if the primary engine solved it (reusable), ``False`` if
        the BV-SAT completeness engine produced the solution instead. On a
        non-OK primary search, falls back to BV-SAT on ``problem_buf``;
        BV-SAT UNSAT raises ``SolveFailure``, UNKNOWN/ERROR raises
        ``BackendInternalError``."""
        from dv_solve.ctx import SOLVE_OK
        seed = randstate.randint(0, (1 << 63) - 1)
        if solve_info is not None:
            solve_info.n_sat_calls += 1
        # fair_pick=True: the stimulus distribution -- uniform over solutions,
        # as IEEE 1800 specifies, with a solve order's stages (declared by
        # _populate_builder) chosen first.
        _t = PT.now()
        rc = ctx.solve(seed=seed, fair_pick=True)
        PT.add("solve", _t)
        if rc == SOLVE_OK:
            _validate_model(ctx, "per-RandSet solve")
            # dv-solve returns an int64; for an unsigned field whose value has its
            # top bit set (only at width 64) that int64 is negative, so reinterpret
            # as unsigned. Signed fields are already correctly sign-extended.
            _t = PT.now()
            if opt_flags.BULK_READBACK and plan is not None and readback:
                # One FFI call for the whole RandSet. Only on the plan-reuse
                # path: the buffers are built once and cached on the plan, so a
                # first (build-path) solve does not pay to construct them.
                bulk = plan.bulk
                if bulk is None:
                    bulk = plan.bulk = _BulkReadback(
                        [(f, vid, int(f.width), bool(f.is_signed))
                         for f, vid in readback])
                bulk.read_into_fields(ctx)
            else:
                for f, vid in readback:
                    f.set_val(self._as_field_value(
                        ctx.get_value(vid), int(f.width), bool(f.is_signed)))
            PT.add("readback", _t)
            return True
        # The native *search* is incomplete on some feasible sets that are not
        # simple intervals (e.g. weak backward propagation for extract/bitwise),
        # so a non-OK search result is NOT a sound proof of unsatisfiability.
        # Hand the same problem to the complete BV-SAT engine for an
        # authoritative verdict (or, if it can't decide, defer externally).
        if problem_buf is not None:
            self._solve_via_bvsat(problem_buf, readback, randstate, solve_info,
                                  make_base=make_base, sample_vars=sample_vars,
                                  has_order=has_order, rand_order_l=rand_order_l,
                                  dist_targets=dist_targets,
                                  cond_dist_targets=cond_dist_targets,
                                  dist_guard_vids=dist_guard_vids, n_softs=n_softs)
            return False
        # Both callers pass the problem buffer (the reuse path from its
        # cached SolveCtx).
        raise BackendInternalError(
            "primary search returned rc=%d with no problem buffer for BV-SAT"
            % rc)

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
                         has_order=False,
                         rand_order_l=None, dist_targets=None,
                         cond_dist_targets=None, dist_guard_vids=None,
                         n_softs=0, retain=None) -> SolveResult:
        """Solve ``problem_buf`` with the internal BV-SAT completeness engine and
        write values back. Authoritative: SAT -> set values & return; UNSAT ->
        ``SolveFailure``; UNKNOWN/ERROR -> ``BackendInternalError`` (the
        translator emits nothing BV-SAT can't decide).

        When a ``make_base`` factory is available, a SAT model is drawn
        through the XOR-hashing uniform sampler (``bvsat_sampler``) so the
        value distribution is usable as stimulus; otherwise the raw
        (clustered) kissat model is read back."""
        from dv_solve.bvsat import (
            BVSatCtx, BVSAT_SAT, BVSAT_UNSAT, maxsat_keepset)
        seed = randstate.randint(0, (1 << 63) - 1)
        if solve_info is not None:
            solve_info.n_sat_calls += 1
        # DSE-2 soft-aware serve. The plain BV-SAT path ignores `softs_head`. For a
        # soft-bearing RandSet, first run the engine's MaxSAT relaxation to fix the
        # maximal priority-respecting kept-soft set (mirroring the primary engine's
        # policy), then enforce exactly that set as hard (`soft_keep`) on the main
        # check AND every sampler draw — so the served model and its distribution
        # honor the kept softs. The kept mask is in `softs_head` walk order and the
        # sampler's `make_base` rebuilds are deterministic, so one mask stays valid
        # across rebuilds (no Python-side soft-index mapping). A soft that conflicts
        # is relaxed by the engine, never dropped silently or enforced as hard.
        soft_keep = None
        if (n_softs == 0 and not has_order and not dist_targets
                and not cond_dist_targets and _BVSAT_SAMPLER
                and make_base is not None and sample_vars):
            # Plain uniform serve: the engine's sampler decides SAT/UNSAT
            # itself (a complete engine), so the problem is blasted once, not
            # once to check and again to sample (V19). `retain` may keep the
            # encoded instance for the next randomize(). UNKNOWN/ERROR fall
            # through to the check below, which reports them.
            from vsc.model.solver import bvsat_sampler
            nb = bvsat_sampler.open_native(problem_buf)
            if nb is not None:
                kept = False
                try:
                    rc = bvsat_sampler.draw_native(
                        nb, readback, sample_vars, seed, solve_info=solve_info)
                    if rc == BVSAT_SAT:
                        kept = retain is not None and retain(nb)
                        return SolveResult(status=0)
                    if rc == BVSAT_UNSAT:
                        raise SolveFailure(
                            "dv-solve BV-SAT engine proved unsatisfiable",
                            "dv-solve BV-SAT engine proved the constraints unsatisfiable")
                finally:
                    if not kept:
                        nb.destroy()
        bb = BVSatCtx(problem_buf)
        try:
            if n_softs > 0:
                rc, soft_keep = maxsat_keepset(problem_buf, seed, n_softs)
                if rc == BVSAT_SAT:
                    # Re-solve the retained bb under the kept set so its readback
                    # model (raw-readback / non-serve paths) honors the kept softs.
                    rc = bb.check(seed=seed, soft_keep=soft_keep)
            else:
                rc = bb.check(seed=seed)
            if rc == BVSAT_UNSAT:
                # Complete engine -> sound UNSAT. dv-solve is now authoritative
                # for UNSAT without needing the external fallback. The Randomizer
                # catches this and re-raises with its own (Boolector-built)
                # diagnostics, so the message here is internal.
                raise SolveFailure(
                    "dv-solve BV-SAT engine proved unsatisfiable",
                    "dv-solve BV-SAT engine proved the constraints unsatisfiable")
            if rc == BVSAT_SAT:
                # Prefer the uniform sampler: kissat's raw model is too clustered
                # for stimulus. The base SAT verdict above guarantees the sampler
                # converges (m==0 is this same satisfiable problem).
                from vsc.model.solver import bvsat_sampler
                if has_order:
                    # Honor `solve_order` natively via *staged* sampling: freeze
                    # each order stage's values before sampling the next, matching
                    # the Boolector swizzler's per-stage assume/assert. A field of
                    # any width is frozen (a wide one as a wide constant, V18).
                    stages = self._order_stages(readback, rand_order_l)
                    if (_BVSAT_SAMPLER and make_base is not None and sample_vars
                            and stages is not None):
                        ok = bvsat_sampler.sample_ordered(
                            make_base, stages, sample_vars, seed,
                            solve_info=solve_info, soft_keep=soft_keep)
                        if ok:
                            return SolveResult(status=0)
                    # Not staged (no sampler, or it gave up, which should
                    # not happen): serve it unordered below. solve_order
                    # shapes the distribution only; the constraints hold.
                if _BVSAT_SAMPLER and make_base is not None and sample_vars:
                    # A dist-bearing RandSet served via BV-SAT (the
                    # primary's add_dist is ignored here): honor the dist
                    # weighting via a weighted assume-then-assert pre-stage
                    # (EF-1b), then uniform-sample the rest. Otherwise the
                    # plain uniform sampler.
                    if cond_dist_targets:
                        # Rand-guarded conditional dist: freeze the guard vars
                        # first, then apply the *active* branch's weighting so
                        # the ratio is guard-correlated (not the uniform mean).
                        ok = bvsat_sampler.sample_dist_conditional(
                            make_base, readback, sample_vars, seed,
                            cond_dist_targets, dist_guard_vids or set(),
                            solve_info=solve_info, soft_keep=soft_keep)
                    elif dist_targets:
                        ok = bvsat_sampler.sample_dist(
                            make_base, readback, sample_vars, seed,
                            dist_targets, solve_info=solve_info,
                            soft_keep=soft_keep)
                    else:
                        ok = bvsat_sampler.sample(
                            make_base, readback, sample_vars, seed,
                            solve_info=solve_info, soft_keep=soft_keep)
                    if ok:
                        return SolveResult(status=0)
                    # Sampler couldn't serve (shouldn't happen): fall through
                    # to the raw readback so we still return a valid model.
                for f, vid in readback:
                    f.set_val(self._bb_value(bb, vid, sample_vars))
                return SolveResult(status=0)
            # UNKNOWN/ERROR: the complete engine could not decide. Its causes
            # are a signed `>>` operand, nesting deeper than 4096, a sum or
            # constant wider than DVS_MAX_WIDTH, a clog2 operand wider than 64
            # bits, a select over undefined vars, a Source group, an env
            # conflict cap (DV_BB_MAX_CONFLICTS) and out-of-memory. The
            # translator emits none of them (pyvsc's own recursion limit stops
            # a deep expression first), so this is a bug, not a fallback (v2
            # plan V22).
            raise BackendInternalError(
                "BV-SAT could not decide a RandSet (verdict %d)" % rc)
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
            if f.width > 64:
                # The constraint narrows the field beyond the int64 add_var
                # envelope (e.g. `a > 2**63` on a 128-bit field). The field is
                # wide, so it is routed to the width-agnostic BV-SAT engine, which
                # gets the real bound from the *translated constraint* (which
                # carries a wide literal). Declare the var free across its
                # int64-capped natural range — assert_var_bounds reads that as "no
                # bound asserted" for a wide var — and let the constraint + BV-SAT
                # decide SAT/UNSAT and the value, instead of deferring
                # (`wide-range`). No gap re-assertion: the original constraint
                # already encodes the bound, and its literal can't round-trip
                # through int64 here anyway.
                return w_lo, w_hi, None
            # width <= 64: the domain lies entirely outside what the field can
            # represent -> unsatisfiable at this width; let the fallback decide.
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

    def _add_dist_for_field(self, b, idmap, f, scopes, tr):
        """Emit the native ``add_dist`` weighting for field ``f`` from its dist
        scope(s), resolving conditional dist (if/else/implies) where possible:

         * One unconditional scope — emit its weighted ``add_dist`` (simple case).
         * All-conditional scopes with solve-time-*constant* guards (e.g. an
           if/else on a non-rand selector): evaluate the guards now and emit the
           *active* branch's ``add_dist``; if no branch is active emit nothing —
           the guarded ``inside`` membership (already compiled) fully constrains
           the field.
         * All-conditional scopes with a *rand* guard (branch not resolvable at
           build time): emit a uniform ``add_dist`` over the *union* of the
           branches' ranges so the value picker still covers the feasible set
           evenly. The conditional *weighting* is dropped (documented
           reduced-distribution guarantee for rand-guarded dist, Phase-B §5) —
           correctness is unaffected since the hard membership is guarded.
         * Several active dists (plain ones plus constant-guard branches whose
           guard holds): Boolector's swizzler picks one of them uniformly per
           call and steers to its weighted target. Over calls that is the
           *mixture* of their distributions, each with probability 1/k, so we
           emit one ``add_dist`` holding every active dist's entries, each
           dist's weights normalised to equal total mass
           (``_mix_dist_entries``). Deterministic, so the plan stays cacheable.
           Each dist's zero-weight values are excluded as hard constraints:
           in a mixture another dist could otherwise give them weight.
         * Any rand-guarded conditional dist (with or without plain ones): a
           guard-staged target (below), the plain dists as always-active
           branches.

        Returns ``(entries, cond_target)``:

         * ``entries`` — the weighted ``DistEntry`` list applied to the primary's
           value picker (captured so the BV-SAT ``sample_dist`` path can honor the
           same weighting when a dist-bearing RandSet force-serves via BV-SAT, which
           ignores ``add_dist`` — e.g. a dist under a conjunctive-body implication,
           EF-1b), or ``None`` when no weighted selection was emitted.
         * ``cond_target`` — for a *rand-guarded* conditional dist, a
           ``{"branches": [(cond_l, entries), ...], "guard_vids": {...}}`` descriptor
           so the guard-staged sampler (``sample_dist_conditional``) can freeze the
           guard first and then apply the *active* branch's weighting. ``None``
           otherwise. When present, the RandSet force-serves via BV-SAT so the
           weighting is guard-correlated rather than dropped.
        """
        conditional = [s for s in scopes if getattr(s, "is_conditional", False)]
        plain = [s for s in scopes if not getattr(s, "is_conditional", False)]

        # Common path: exactly one unconditional dist.
        if len(scopes) == 1 and not conditional:
            entries = self._dist_entries(f, scopes[0].dist_c)
            self._exclude_zero_weight(b, f, [entries], tr)
            if entries:
                _native_dist(b, idmap.id_of(f), f, entries)
                return entries, None
            return None, None

        rand_guarded = [s for s in conditional
                        if _guard_references_rand(getattr(s, "cond_l", []))]
        if plain and not rand_guarded:
            active = plain + [s for s in conditional
                              if self._guard_true(getattr(s, "cond_l", []))]
            return self._emit_dist_mixture(b, idmap, f, active, tr)

        # A rand guard can't be resolved at build time. Rather than drop the
        # weighting to a uniform union (the old Phase-B §5 reduced-distribution
        # behavior), build a guard-staged conditional target: the sampler
        # freezes the guards, then applies the mixture of the dists active
        # under them. A plain dist is a branch whose (empty) guard always
        # holds. Each dist's zero-weight values are excluded under its guard,
        # since a mixture drops them (_mix_dist_entries). Still emit the
        # uniform union as the native primary's fallback picker (it is ignored
        # on the BV-SAT serve path but keeps the non-served path sound).
        if rand_guarded:
            branches = []
            guard_vids = set()
            union = []
            for s in plain + conditional:
                cond_l = getattr(s, "cond_l", []) \
                    if getattr(s, "is_conditional", False) else []
                br_entries = self._dist_entries(f, s.dist_c)
                branches.append((cond_l, br_entries))
                guard_vids |= _guard_field_vids(cond_l, idmap)
                self._exclude_zero_weight(b, f, [br_entries], tr, cond_l)
                for e in br_entries:
                    union.append({**e, "weight": 1})
            if union:
                _native_dist(b, idmap.id_of(f), f, union)
            if branches and guard_vids:
                return None, {"branches": branches, "guard_vids": guard_vids}
            return None, None            # no stageable guard → weighting dropped

        # Constant guards: keep the branch(es) whose guard currently holds.
        active = [s for s in conditional
                  if self._guard_true(getattr(s, "cond_l", []))]
        return self._emit_dist_mixture(b, idmap, f, active, tr)

    def _emit_dist_mixture(self, b, idmap, f, active, tr):
        """Emit the weighting for the ``active`` dist scopes of field ``f``:
        none → nothing (the membership suffices); one → its entries as they
        are; several → their mixture (see ``_add_dist_for_field``)."""
        if not active:
            return None, None
        per = [self._dist_entries(f, s.dist_c) for s in active]
        self._exclude_zero_weight(b, f, per, tr)
        entries = per[0] if len(per) == 1 else _mix_dist_entries(per)
        if entries:
            _native_dist(b, idmap.id_of(f), f, entries)
            return entries, None
        return None, None

    @staticmethod
    def _exclude_zero_weight(b, f, per, tr, cond_l=()):
        """Assert ``f`` outside every zero-weight entry of every dist in
        ``per`` (``f < lo || f > hi``), under the guard ``cond_l`` when one is
        given, as Boolector's dist expansion does. The engine's ``add_dist``
        only gives such an entry no mass: a value another entry also covers
        (``[0:255] :/ 1, 0 := 0``) kept that entry's mass, and the BV-SAT
        samplers, which serve every dist on a field over 64 bits, ignore
        ``add_dist``. A mixture drops zero-weight entries altogether."""
        from vsc.model.expr_bin_model import ExprBinModel
        from vsc.model.expr_fieldref_model import ExprFieldRefModel
        from vsc.model.expr_literal_model import ExprLiteralModel
        from vsc.model.bin_expr_type import BinExprType
        from dv_solve.problem import BIN_AND, BIN_OR, UN_NOT
        guard = None
        for c in cond_l:
            g = _guard_ref(tr, c)
            guard = g if guard is None else b.expr_binary(BIN_AND, guard, g)
        seen = set()
        for entries in per:
            for e in entries:
                key = (e["lo"], e["hi"])
                if e["weight"] or key in seen:
                    continue
                seen.add(key)
                lo = ExprLiteralModel(e["lo"], f.is_signed, f.width)
                hi = ExprLiteralModel(e["hi"], f.is_signed, f.width)
                below = ExprBinModel(ExprFieldRefModel(f), BinExprType.Lt, lo)
                above = ExprBinModel(ExprFieldRefModel(f), BinExprType.Gt, hi)
                outside = tr.translate(
                    ExprBinModel(below, BinExprType.Or, above))
                if guard is not None:
                    outside = b.expr_binary(
                        BIN_OR, b.expr_unary(UN_NOT, guard), outside)
                b.add_constraint(outside)

    @staticmethod
    def _guard_true(cond_l):
        """True iff every guard expression in ``cond_l`` currently evaluates true.
        Only meaningful for solve-time-constant guards (see
        ``_guard_references_rand``). Handles the ``Not(..)`` wrapper the if/else
        builder puts on a false branch — ``ExprUnaryModel`` has no ``val()`` — by
        recursing into the operand."""
        from vsc.model.expr_unary_model import ExprUnaryModel
        from vsc.model.unary_expr_type import UnaryExprType

        def _eval(cond):
            if isinstance(cond, ExprUnaryModel) and cond.op == UnaryExprType.Not:
                return not _eval(cond.expr)
            return bool(int(cond.val()))

        try:
            return all(_eval(c) for c in cond_l)
        except Exception:
            # A guard we can't evaluate → treat as not-satisfied so we never
            # over-apply weighting (the membership still guarantees correctness).
            return False

    def _dist_entries(self, field, dist_c):
        """Translate a ``ConstraintDistModel`` into native ``add_dist``
        ``DistEntry`` dicts.

        Each ``DistWeightExprModel`` becomes one entry: a single value → a
        ``[v, v]`` per-value entry; a range → a ``[lo, hi]`` entry whose
        ``is_per_value`` follows the ``:=``/``:/`` flag. Zero-weight entries are
        kept (the caller also excludes their values as hard constraints,
        ``_exclude_zero_weight``); a negative weight counts as zero, as on
        Boolector. An entry is clipped to the field's domain, or dropped when
        none of it is in the domain: a value the field can't hold can't be
        chosen, which is what the engine already does with one inside int64
        (and keeps every bound of a <= 64-bit field inside int64). A wider
        field's entries are not given to the engine (``_native_dist``); its
        RandSet is served by BV-SAT, whose samplers draw from them."""
        w_f = int(field.width)
        if field.is_signed:
            dom_lo, dom_hi = -(1 << (w_f - 1)), (1 << (w_f - 1)) - 1
        else:
            dom_lo, dom_hi = 0, (1 << w_f) - 1
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
            except Exception as e:
                raise BackendInternalError(
                    "dist on '%s': cannot evaluate a weight or range (%s)" % (
                        getattr(field, "name", "?"), e))
            if hi < lo:
                lo, hi = hi, lo
            lo, hi = max(lo, dom_lo), min(hi, dom_hi)
            if lo > hi:
                continue
            entries.append({"lo": lo, "hi": hi, "weight": max(weight, 0),
                            "is_per_value": is_per_value})
        return _fit_weights_u32(entries)
