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

# Created on Jan 21, 2020
#
# @author: ballance


import os
import random
import sys
import time
from typing import List, Dict

from vsc.constraints import constraint, soft
from vsc.model.bin_expr_type import BinExprType
from vsc.model.constraint_model import ConstraintModel
from vsc.model.constraint_soft_model import ConstraintSoftModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.expr_model import ExprModel
from vsc.model.field_model import FieldModel
from vsc.model.field_scalar_model import FieldScalarModel
from vsc.model.model_visitor import ModelVisitor
from vsc.model.rand_if import RandIF
from vsc.model.rand_info import RandInfo
from vsc.model.rand_info_builder import RandInfoBuilder
from vsc.model.variable_bound_model import VariableBoundModel
from vsc.model.separability import t0_promote
from vsc.visitors.array_constraint_builder import ArrayConstraintBuilder
from vsc.visitors.constraint_override_rollback_visitor import ConstraintOverrideRollbackVisitor
from vsc.visitors import constraint_override_visitor as constraint_override
from vsc.visitors.dist_constraint_builder import DistConstraintBuilder
from vsc.visitors.model_pretty_printer import ModelPrettyPrinter
from vsc.visitors.variable_bound_visitor import VariableBoundVisitor
from vsc.visitors.dynamic_expr_reset_visitor import DynamicExprResetVisitor
from vsc.model.solve_failure import SolveFailure
from vsc.visitors.ref_fields_postrand_visitor import RefFieldsPostRandVisitor
from vsc.model.rand_set_dispose_visitor import RandSetDisposeVisitor
from vsc.visitors.clear_soft_priority_visitor import ClearSoftPriorityVisitor
from vsc.profile import randomize_start, randomize_done, profile_on
from vsc.model.source_info import SourceInfo
from vsc.profile.solve_info import SolveInfo
from vsc.visitors.lint_visitor import LintVisitor
from vsc.model.solver.backend import SolverBackendIF, BackendIncomplete, select_backend
from vsc.model.solver import xcheck
from vsc.impl.ctor import glbl_debug, glbl_solvefail_debug, get_solver_backend
from vsc.model import phase_timers as PT
from vsc.model import opt_flags


# ---------------------------------------------------------------------------
# Object-level "randomization plan" cache (perf P2/3 — see
# doc/notes/dv_solve_performance_plan.md §4).
#
# For a static object randomized repeatedly, the pre-solve pipeline
# (VariableBoundVisitor + array expansion + RandInfoBuilder partition) re-derives
# an identical bound_m + RandInfo every call. When the object is "Tier-A eligible"
# (no covergroup steering, no dist, no arrays, no inline constraints) those passes
# are pure functions of the structure + referenced non-rand values + `inside`
# rangelist contents, all of which the plan signature captures, so we cache
# (bound_m, ri) on the root object and skip the passes while the signature still
# matches. Reuse is byte-identical to the non-cached path (or it rebuilds); the
# per-RandSet compiled-problem cache (P1) lives underneath. Disable with
# VSC_DVSOLVE_PLAN_CACHE=0.
# ---------------------------------------------------------------------------
_PLAN_CACHE_ENABLED = os.environ.get("VSC_DVSOLVE_PLAN_CACHE", "1") != "0"
_PLAN_ATTR = "_vsc_rand_plan"

# Extend the Tier-A plan cache to fixed-size array / `foreach` models (default
# on; kill-switch VSC_DVSOLVE_ARRAY_PLAN_CACHE=0). Without it, `foreach` expansion
# rebuilds fresh constraint objects every randomize() so the compiled-problem
# cache never hits — arr[128] rebuilds all 128 partitions every call (~7x slower).
# Safe because is_fresh() catches the array-specific change modes: element-count
# changes (append/resize/override) via array_state, plus rand_mode/value/
# constraint_mode/rangelist/dist via the existing snapshots. Rand-SIZED arrays
# change structure per call and stay ineligible. See
# doc/notes/dv_solve_native_full_problem_plan.md (§0 reconstruction finding).
_ARRAY_PLAN_CACHE = os.environ.get("VSC_DVSOLVE_ARRAY_PLAN_CACHE", "1") != "0"

# Whole-problem merged solve (default on; kill-switch VSC_DVSOLVE_MERGE=0). On a
# plan-cache hit, solve all independent RandSets in ONE native problem (reusing a
# ctx cached on the plan) instead of the per-RandSet loop — ~9x on a large
# many-partition warm solve, since the per-RandSet reuse-signature / dispatch /
# dispose overhead dominates once the compiled problem is cached. Only the
# dv-solve back-end implements ``solve_merged``; special RandSets (dist / order /
# soft / >64-bit) fall back to the per-RandSet path. See
# doc/notes/dv_solve_native_full_problem_plan.md.
_MERGE_ENABLED = os.environ.get("VSC_DVSOLVE_MERGE", "1") != "0"

# T0 tier: no-solver direct draw (default on; kill-switch VSC_T0=0). A RandSet
# whose every rand field is separable and constrained only by expressions with
# an exactly-computable value set is promoted into ri.unconstrained_l and drawn
# uniformly over that set — which is the distribution the solver is meant to
# produce for such a RandSet, and is why the promotion is legal. Eligibility is
# decided in vsc.model.separability and is conservative: anything unrecognized
# stays on the solver. Back-end independent (it operates on the RandInfo), so
# the classic and dataclass front-ends get it alike.
_T0_ENABLED = os.environ.get("VSC_T0", "1") != "0"

# Strict no-fallback mode (feature-completeness plan, Phase 0). When set, the
# Randomizer does NOT fall back from the primary back-end to another on
# BackendIncomplete — it re-raises, so any residual dependence on the fallback
# back-end (e.g. Boolector) surfaces loudly in CI. Used to enumerate and
# burn down the remaining defers per phase. Off by default.
_NO_FALLBACK = os.environ.get("VSC_DVSOLVE_NO_FALLBACK", "0") != "0"

# Always-on fallback histogram (feature-completeness plan, Phase E / P0-T). The
# per-call SolveInfo histogram (profile/solve_info.py) only exists when profiling
# is on; this module-level tally lets a test (or a user) collect the reason-code
# histogram across an entire run without enabling full profiling. Gated by
# VSC_DVSOLVE_FALLBACK_TALLY=1 so it is zero-overhead off by default. Each entry
# is keyed by "<reason_code>" for a defer the next back-end served and
# "<reason_code>:hard" for a defer no back-end could serve (re-raised).
_FALLBACK_TALLY_ENABLED = os.environ.get("VSC_DVSOLVE_FALLBACK_TALLY", "0") != "0"
_FALLBACK_TALLY = {}


def record_fallback(reason_code, served=True):
    """Record one back-end deferral in the process-global tally. ``served``
    distinguishes a defer the next back-end satisfied from a hard-fail (no
    back-end could serve → re-raised). No-op unless VSC_DVSOLVE_FALLBACK_TALLY=1
    (or the tally was force-enabled by a harness via ``set_fallback_tally``)."""
    if not _FALLBACK_TALLY_ENABLED:
        return
    key = reason_code if served else "%s:hard" % reason_code
    _FALLBACK_TALLY[key] = _FALLBACK_TALLY.get(key, 0) + 1


def get_fallback_tally():
    """Return a copy of the current fallback histogram (reason_code -> count)."""
    return dict(_FALLBACK_TALLY)


def reset_fallback_tally():
    """Clear the fallback histogram (call before a measured run)."""
    _FALLBACK_TALLY.clear()


def set_fallback_tally(enabled):
    """Force the always-on tally on/off programmatically (for test harnesses
    that don't want to rely on the env var). Returns the previous setting."""
    global _FALLBACK_TALLY_ENABLED
    prev = _FALLBACK_TALLY_ENABLED
    _FALLBACK_TALLY_ENABLED = bool(enabled)
    return prev


def snapshot_fallback_tally():
    """Capture the full tally state — ``(enabled, counts)`` — so a test that needs
    to measure its *own* corpus (reset + accumulate) can restore the prior state
    afterward via ``restore_fallback_tally``. Without this a per-test measurement
    clears the process-global accumulator and corrupts a suite-wide audit run
    (the F-0a self-sufficiency audit). Good citizens snapshot on entry, restore on
    exit, so their synthetic deferrals never pollute the suite-wide number."""
    return (_FALLBACK_TALLY_ENABLED, dict(_FALLBACK_TALLY))


def restore_fallback_tally(snap):
    """Restore a state captured by ``snapshot_fallback_tally``."""
    global _FALLBACK_TALLY_ENABLED
    enabled, counts = snap
    _FALLBACK_TALLY_ENABLED = bool(enabled)
    _FALLBACK_TALLY.clear()
    _FALLBACK_TALLY.update(counts)


class _RandPlan(object):
    """Cached pre-solve plan for one root model object (Tier-A)."""

    __slots__ = ("bound_m", "ri", "field_state", "block_state",
                 "rangelist_state", "dist_state", "soft_priority_state",
                 "array_state", "merged", "draw_plan", "_keepalive")

    def __init__(self, bound_m, ri, field_state, block_state, rangelist_state,
                 dist_state, keepalive, array_state=()):
        self.bound_m = bound_m
        self.ri = ri
        # array_state: list of (FieldArrayModel, element_count). Detects an
        # array whose length changed (append/resize/list-override) between calls
        # — the cached plan holds the first build's expanded `foreach`
        # constraints, which no longer cover a resized array. See
        # _collect_array_state.
        self.array_state = array_state
        # merged: whole-problem merged solve state (dv-solve). None = untried,
        # False = not mergeable (special randset → per-RandSet path), else a
        # backend-owned (ctx, readback) cache reused across randomizes. Built
        # lazily by the back-end on first solve; freed when the plan is evicted.
        self.merged = None
        # draw_plan: cached (fast_lane, rest) split of the unconstrained draw
        # (see _build_draw_plan). Built lazily on the first solve. A new plan
        # object is created on every rebuild, so there is nothing to invalidate
        # -- and a rand_mode change, which is what would change the split, is
        # already a freshness miss.
        self.draw_plan = None
        # soft_priority_state: list of (ConstraintModel, priority). Soft-constraint
        # priorities are (re)accumulated by RandInfoBuilder, which a Tier-A hit
        # SKIPS — yet `clear_soft_priority` at the top of every randomize() still
        # zeroes them. Snapshot the correct priorities here (RandInfoBuilder has
        # just run) and re-apply them on a hit (restore_soft_priorities), so the
        # relaxation order survives caching. Without this, cached iterations see
        # all-zero priorities and the back-end keeps the wrong soft.
        self.soft_priority_state = [
            (c, c.priority)
            for rs in ri.all_randsets()
            for c in rs.soft_constraints()]
        # field_state: list of (field, was_used_rand, value_if_nonrand). Detects
        # rand_mode toggles (is_used_rand) and changes to referenced non-rand
        # values (which bake into bound_m / constants).
        self.field_state = field_state
        # block_state: list of (ConstraintBlockModel, enabled). Detects
        # constraint_mode enable/disable.
        self.block_state = block_state
        # rangelist_state: list of (ExprRangelistModel, snapshot). Detects an
        # `inside` rangelist whose contents were mutated between calls.
        self.rangelist_state = rangelist_state
        # dist_state: list of (ConstraintDistScopeModel, snapshot). Detects a
        # `dist` weight/range change the back-end bakes into native add_dist
        # (incl. dynamic weights whose field is absent from field_state).
        self.dist_state = dist_state
        # Hold strong refs to every object whose identity/state the signature
        # reads, so Python can't recycle an id and cause a false match.
        self._keepalive = keepalive

    def restore_soft_priorities(self):
        """Re-apply the cached soft-constraint priorities. Called on a Tier-A hit
        after `clear_soft_priority` has zeroed them and RandInfoBuilder (which
        would re-accumulate them) was skipped."""
        for c, p in self.soft_priority_state:
            c.priority = p

    def is_fresh(self):
        for arr_fm, count in self.array_state:
            if len(arr_fm.field_l) != count:
                return False              # array resized -> expansion stale
        for f, was_rand, val in self.field_state:
            if f.is_used_rand != was_rand:
                return False
            # val is None when the value is not tracked: either the field is
            # used-rand (the solver owns it) or, under S1.7, no constraint in
            # the plan reads it.
            if val is not None and int(f.get_val()) != val:
                return False
        for blk, en in self.block_state:
            if blk.enabled != en:
                return False
        for rlm, snap in self.rangelist_state:
            if _snapshot_rangelist(rlm) != snap:
                return False
        for scope, snap in self.dist_state:
            if _snapshot_dist(scope) != snap:
                return False
        return True


def _collect_constraint_blocks(field_model_l):
    """All ConstraintBlockModels reachable from the given fields (composite
    fields carry them in constraint_model_l; recurse into sub-fields)."""
    from vsc.model.field_composite_model import FieldCompositeModel
    blocks = []
    stack = list(field_model_l)
    seen = set()
    while stack:
        fm = stack.pop()
        if id(fm) in seen:
            continue
        seen.add(id(fm))
        cml = getattr(fm, "constraint_model_l", None)
        if cml:
            blocks.extend(cml)
        sub = getattr(fm, "field_l", None)
        if sub:
            stack.extend(sub)
    return blocks


def _has_uncacheable_expansion(ri):
    """True if a RandSet holds a rollback-fragile array expansion — a surviving
    `foreach` or an in-place `ConstraintOverrideModel`. A plain top-level
    `foreach` expands to flat per-element `ConstraintExprModel`s that persist, so
    the cached `ri` stays valid across calls. But a `foreach` nested in a scope
    (e.g. gated by an `if_then`, or over an empty array) is expanded via an
    in-place override that ``ConstraintOverrideRollbackVisitor`` reverts after
    every randomize — so the cached `ri` would revert to the unexpanded (and to
    dv-solve unsolvable) form on reuse. Exclude those from the plan cache."""
    from vsc.model.constraint_foreach_model import ConstraintForeachModel
    from vsc.model.constraint_override_model import ConstraintOverrideModel
    stack = []
    for rs in ri.all_randsets():
        stack.extend(rs.constraints())
    seen = set()
    while stack:
        c = stack.pop()
        if id(c) in seen:
            continue
        seen.add(id(c))
        if isinstance(c, (ConstraintForeachModel, ConstraintOverrideModel)):
            return True
        for attr in ("constraint_l", "true_c", "false_c"):
            v = getattr(c, attr, None)
            if v is None:
                continue
            stack.extend(v if isinstance(v, list) else [v])
    return False


class _RangelistCollector(ModelVisitor):
    """Collect every ExprRangelistModel reachable from a constraint block."""

    def __init__(self):
        super().__init__()
        self.rangelists = []

    def visit_expr_rangelist(self, r):
        self.rangelists.append(r)
        super().visit_expr_rangelist(r)


class _RefsUsedRand(ModelVisitor):
    """Does this expression read any field the solver owns this call?"""

    def __init__(self):
        super().__init__()
        self.found = False

    def visit_expr_fieldref(self, e):
        if getattr(e.fm, "is_used_rand", False):
            self.found = True


#: Placeholder for a rangelist bound the solver owns (see _snapshot_rangelist).
_SOLVER_OWNED = object()


def _bound_snap(e):
    """Snapshot one rangelist bound: its value, or `_SOLVER_OWNED` if it reads a
    used-rand field.

    A symbolic bound — `rng(self.c, self.d)` with `c`/`d` rand — is not a
    *user* input: the solver re-derives it from the constraints (which are in
    the plan) on every call. Snapshotting its evaluated value makes the
    signature compare this solve's inputs against the *previous solve's answer*,
    so the plan is never fresh and is rebuilt every time.

    Measured: `vdc_in` (`b inside rng(c, d)`, c/d rand) rebuilt its plan on
    29/29 consecutive randomizes, costing **7.7x** on the create-many path
    (37 992 -> 4 941 solves/sec). S1.3 exposed this by leaving the model holding
    the previous solution instead of the fresh instance's zeros, but the warm
    path was already thrashing the same way before Stage 1 — which is the
    long-standing `in_kw` anomaly in RESULTS_constrainedrandom.md §4.

    Same principle as S1.7: state the solver owns must not participate in
    freshness, only state the *user* can change between calls (literals, or
    refs to non-rand fields, which `field_state` tracks separately).
    """
    v = _RefsUsedRand()
    e.accept(v)
    if v.found:
        return _SOLVER_OWNED
    return int(e.val())


def _snapshot_rangelist(rlm):
    """A hashable snapshot of a rangelist's current range bounds, or None if a
    bound can't be evaluated to an int (→ caller treats the object as
    ineligible). `inside` rangelists are the one mutable input to bound_m that
    field_state doesn't capture: the rangelist object is stable but `o.rl.clear()
    / .extend(...)` rebuilds its range literals in place."""
    narrow = opt_flags.NARROW_PLAN_SIG
    snap = []
    for item in rlm.rl:
        lhs = getattr(item, "lhs", None)
        rhs = getattr(item, "rhs", None)
        try:
            if narrow:
                if lhs is not None and rhs is not None:
                    snap.append((_bound_snap(lhs), _bound_snap(rhs)))
                else:
                    snap.append((_bound_snap(item),))
            elif lhs is not None and rhs is not None:
                snap.append((int(lhs.val()), int(rhs.val())))
            else:
                snap.append((int(item.val()),))
        except Exception:
            return None
    return tuple(snap)


def _collect_rangelist_state(blocks):
    """[(ExprRangelistModel, snapshot)] for every rangelist in the blocks, or
    None if any rangelist can't be snapshotted (→ object is ineligible)."""
    coll = _RangelistCollector()
    for b in blocks:
        b.accept(coll)
    state = []
    for rlm in coll.rangelists:
        snap = _snapshot_rangelist(rlm)
        if snap is None:
            return None
        state.append((rlm, snap))
    return state


class _DistScopeCollector(ModelVisitor):
    """Collect every ConstraintDistScopeModel reachable from a constraint block
    (the expanded form of a `dist` constraint)."""

    def __init__(self):
        super().__init__()
        self.scopes = []

    def visit_constraint_dist_scope(self, s):
        self.scopes.append(s)
        super().visit_constraint_dist_scope(s)


def _snapshot_dist(scope):
    """A hashable snapshot of a dist scope's weight entries
    ``(lo, hi, weight, is_per_value)``, or None if any bound/weight can't be
    evaluated to an int. dist weights are a mutable input to the *native*
    compiled problem (the back-end bakes them into ``add_dist``) that
    ``field_state`` does NOT capture: a dynamic weight like ``weight(1, en_one)``
    reads ``en_one`` — a field that may not even appear in ``bound_m`` — so a
    weight change is invisible to the field/rangelist snapshots and must be
    tracked here for the cached plan to stay correct."""
    snap = []
    for w in scope.dist_c.weights:
        try:
            lo = int(w.rng_lhs.val())
            hi = int(w.rng_rhs.val()) if w.rng_rhs is not None else lo
            wt = int(w.weight.val())
        except Exception:
            return None
        snap.append((lo, hi, wt, bool(getattr(w, "is_per_value", lo == hi))))
    return tuple(snap)


def _collect_dist_state(blocks):
    """[(ConstraintDistScopeModel, snapshot)] for every dist scope in the
    blocks, or None if any can't be snapshotted (→ object is ineligible)."""
    coll = _DistScopeCollector()
    for b in blocks:
        b.accept(coll)
    state = []
    for scope in coll.scopes:
        snap = _snapshot_dist(scope)
        if snap is None:
            return None
        state.append((scope, snap))
    return state


def _model_has_array(field_model_l):
    """True if any field (recursively) is an array. Array (`foreach`) constraints
    are expanded via in-place constraint *overrides* — which don't grow
    constraint_l — and the expansion can reference mutable external state (e.g. a
    `rangelist` whose contents change between calls), neither of which the
    plan signature captures. So arrays make an object plan-cache-ineligible.

    Used only when the array plan cache is disabled (`_ARRAY_PLAN_CACHE`); when
    enabled, `_collect_array_state` handles arrays with a freshness snapshot
    instead of a blanket veto."""
    from vsc.model.field_array_model import FieldArrayModel
    stack = list(field_model_l)
    seen = set()
    while stack:
        fm = stack.pop()
        if id(fm) in seen:
            continue
        seen.add(id(fm))
        if isinstance(fm, FieldArrayModel):
            return True
        sub = getattr(fm, "field_l", None)
        if sub:
            stack.extend(sub)
    return False


def _collect_array_state(field_model_l):
    """Snapshot every array field's element count and detect rand-sized arrays.

    Returns ``(array_state, has_rand_sized)`` where ``array_state`` is a list of
    ``(FieldArrayModel, element_count)``. A cached plan holds the first build's
    expanded `foreach` constraints (stable across calls for a fixed-size array);
    ``is_fresh()`` compares these counts so an append / resize / list-override
    that changes an array's length invalidates the plan and forces a rebuild.
    A rand-SIZED array re-elaborates its size every call, so it is never cached
    (``has_rand_sized`` → ineligible)."""
    from vsc.model.field_array_model import FieldArrayModel
    array_state = []
    has_rand_sized = False
    stack = list(field_model_l)
    seen = set()
    while stack:
        fm = stack.pop()
        if id(fm) in seen:
            continue
        seen.add(id(fm))
        if isinstance(fm, FieldArrayModel):
            array_state.append((fm, len(fm.field_l)))
            if getattr(fm, "is_rand_sz", False):
                has_rand_sized = True
        sub = getattr(fm, "field_l", None)
        if sub:
            stack.extend(sub)
    return array_state, has_rand_sized


def _build_draw_plan(ri, bound_m):
    """Split the used-rand unconstrained fields into a fast lane and the rest.

    A fast-lane entry is ``(value_obj, lo, n, k, field)`` for a plain scalar
    over one contiguous range: ``n`` values starting at ``lo``, drawn with
    ``k = (n-1).bit_length()`` random bits and rejection. Hoisting the
    ``ValueScalar`` and the range arithmetic out of the per-call loop removes a
    dict lookup, three attribute hops and two type checks per field per
    randomize; on a plan-cached object it is computed once.

    ``field.val`` is captured directly, which is sound because ``set_val``
    mutates ``val.v`` and nothing ever rebinds ``val`` on a FieldScalarModel
    (EnumFieldModel does in its constructor, before any draw, and is excluded
    here by the exact-type check anyway).

    Anything else -- multi-range domain, *empty* domain (the declared-domain
    UNSAT case, which the general loop reports), enum, composite -- goes to the
    second list and takes the unchanged general path.
    """
    fast = []
    rest = []
    for f in ri.unconstrained():
        if not f.is_used_rand:
            continue
        range_l = bound_m[f].domain.range_l
        if len(range_l) == 1 and type(f) is FieldScalarModel:
            lo, hi = range_l[0][0], range_l[0][1]
            n = hi - lo + 1
            fast.append((f.val, lo, n, (n - 1).bit_length(), f))
        else:
            rest.append(f)
    return fast, rest


def _plan_eligible(field_model_l, ri, arrays_expanded, dist_native=False):
    """Tier-A eligibility: no per-call pipeline behavior. (Inline constraints and
    backend gating are checked by the caller.)"""
    if _ARRAY_PLAN_CACHE:
        # Fixed-size arrays are cacheable: the first build's expanded `foreach`
        # constraints are stable across calls, and is_fresh() catches every
        # change mode (element counts via array_state; rand_mode / non-rand
        # values / constraint_mode / rangelist / dist via the other snapshots).
        # Only rand-sized arrays — which re-elaborate their length per call —
        # stay ineligible.
        _, has_rand_sized = _collect_array_state(field_model_l)
        if has_rand_sized:
            return False
        # A rollback-fragile expansion (surviving `foreach` / in-place override,
        # e.g. a scoped or gated `foreach`) reverts after each randomize, so the
        # cached ri would be stale on reuse.
        if _has_uncacheable_expansion(ri):
            return False
    else:
        if arrays_expanded:
            return False                  # array expansion grew constraint_l
        if _model_has_array(field_model_l):
            return False                  # array overrides / mutable refs
    for fm in field_model_l:
        if type(fm).__name__ == "GeneratorModel":
            return False                  # coverage steering is per-call
    for rs in ri.all_randsets():
        dist_field_m = getattr(rs, "dist_field_m", None)
        if not dist_field_m:
            continue
        if not dist_native:
            # The Boolector swizzler chooses a dist target per call (consuming
            # randstate), so a cached plan can't reproduce it. A native back-end
            # instead does the weighted pick inside solve(seed) from a
            # per-call-invariant compiled problem, so dist *is* cacheable —
            # provided is_fresh() re-checks the weight snapshot
            # (_collect_dist_state).
            return False
        for f, scopes in dist_field_m.items():
            # Only a single, unconditional dist is handled natively and is
            # per-call-invariant. Conditional dists (re-elaborated each call,
            # served by the fallback) and multiple dists on one field are NOT
            # cacheable — leave them Tier-B so their per-call expansion runs.
            if len(scopes) != 1 or getattr(scopes[0], "is_conditional", False):
                return False
    return True


class Randomizer(RandIF):
    """Implements the core randomization algorithm"""
    
    EN_DEBUG = False
    
    def __init__(self, randstate, debug=0, lint=0, solve_fail_debug=0, solve_info=None, backend=None):
        self.randstate = randstate
        self.pretty_printer = ModelPrettyPrinter()
        self.solve_info = solve_info
        self.debug = debug
        if glbl_debug > 0 and glbl_debug > debug:
            self.debug = glbl_debug

        self.lint = lint
        self.solve_fail_debug = solve_fail_debug
        if glbl_solvefail_debug > 0 and glbl_solvefail_debug > solve_fail_debug:
            self.solve_fail_debug = glbl_solvefail_debug

        # The solve back-end. do_randomize resolves and passes one in; direct
        # constructions (e.g. unit tests) fall back to the configured default.
        if backend is None:
            backend = select_backend(get_solver_backend())
        self.backend : SolverBackendIF = backend

        # Fallback chain: if the primary back-end reports BackendIncomplete for
        # a RandSet (a construct it can't yet handle), retry that RandSet on the
        # next available back-end. Boolector handles the full feature set, so it
        # is the fallback when the primary is something else.
        self.fallback_backends = []
        if self.backend.name != "boolector":
            try:
                self.fallback_backends.append(select_backend("boolector"))
            except Exception:
                pass

        # Tell the primary whether an external fallback will serve what it can't,
        # so its `auto` serve-SAT mode serves SAT itself only when nothing else
        # will (F-1a). Harmless on back-ends that ignore the attribute.
        self.backend._external_fallback_available = bool(self.fallback_backends)
    
    _state_p = [0,1]
    _rng = None
    
    def _draw_multi_range(self, range_l):
        """Draw uniformly from the union of ``range_l`` (a list of inclusive
        ``[lo, hi]`` pairs).

        Every value in the union is equally likely: one index is drawn across the
        *total* value count and then mapped to (range, offset), so a 1-value range
        and a 1000-value range are weighted 1:1000, not 1:1.

        Previously this picked a range index uniformly and then returned that
        range's **lower endpoint**, so a genuine multi-range domain collapsed onto
        the range minima and every interior value was unreachable. That was
        harmless only for the enumerated case it was written for, where each range
        holds a single value -- and that case is preserved exactly here: when every
        range is a point, ``total == len(range_l)`` and this draws the same index
        from the same span, so enum results are bit-identical.

        One ``randstate`` call, as before, so downstream draws stay aligned.
        """
        total = 0
        for lo, hi in range_l:
            total += hi - lo + 1
        if total <= 0:
            # Degenerate/empty domain: preserve the old behaviour rather than
            # raising here -- the solve path reports the real failure.
            return range_l[0][0]
        # Deliberately `randint`, not the faster `draw`: the enum shape's
        # bit-identity guarantee documented above is relative to this call, and
        # multi-range draws are not the hot path (the contiguous single-range
        # case, which is, has its own fast lane in randomize()).
        k = self.randstate.randint(0, total - 1)
        for lo, hi in range_l:
            n = hi - lo + 1
            if k < n:
                return lo + k
            k -= n
        return range_l[-1][1]

    def randomize(self, ri : RandInfo, bound_m : Dict[FieldModel,VariableBoundModel],
                  plan=None):
        """Randomize the variables and constraints in a RandInfo collection"""
        
        if self.solve_info is not None:
            self.solve_info.n_randsets = len(ri.randsets())
        
        if self.debug > 0:
            rs_i = 0
            while rs_i < len(ri.randsets()):
                rs = ri.randsets()[rs_i]
                print("RandSet[%d]" % rs_i)
                for f in rs.all_fields():
                    if f in bound_m.keys():
                        print("  Field: %s is_rand=%s %s" % (f.fullname, str(f.is_used_rand), str(bound_m[f].domain.range_l)))
                    else:
                        print("  Field: %s is_rand=%s (unbounded)" % (f.fullname, str(f.is_used_rand)))
                        
                for c in rs.constraints():
                    print("  Constraint: " + self.pretty_printer.do_print(c, show_exp=True))
                for c in rs.soft_constraints():
                    print("  SoftConstraint: " + self.pretty_printer.do_print(c, show_exp=True))
                    
                rs_i += 1
                    
            for uf in ri.unconstrained():
                print("Unconstrained: " + uf.fullname)
               
        # Assign values to the unconstrained fields first.
        #
        # After T0 promotion this loop *is* the work on an array model, so it
        # runs off a precomputed plan (see _build_draw_plan) rather than
        # re-deriving each field's range every call. Everything unusual
        # (multi-range, empty, non-scalar, debug) falls through to the general
        # loop below, unchanged.
        _t = PT.now()
        if self.debug > 0:
            fast_l = ()
            uc_rand = list(filter(lambda f:f.is_used_rand, ri.unconstrained()))
        elif plan is not None:
            if plan.draw_plan is None:
                plan.draw_plan = _build_draw_plan(ri, bound_m)
            fast_l, uc_rand = plan.draw_plan
        else:
            fast_l, uc_rand = _build_draw_plan(ri, bound_m)

        if fast_l:
            # Inlined uniform rejection draw. Calling RandState.draw per field
            # instead costs 6.4x as much (19.5 us vs 3.0 us for 128 fields) --
            # at these rates the method call and attribute hops dominate the
            # random-number generation. k == 0 for a point domain, and
            # getrandbits(0) is 0, so that case needs no branch.
            getrandbits = self.randstate.rng.getrandbits
            for val, lo, n, k, f in fast_l:
                v = getrandbits(k)
                while v >= n:
                    v = getrandbits(k)
                val.v = lo + v
                # set_used_rand(False, 0) on a scalar reduces to
                # `is_used_rand = False and (...)` — always plain False.
                f.is_used_rand = False

        for uf in uc_rand:
            if self.debug > 0:
                print("Randomizing unconstrained: " + uf.fullname)
            bounds = bound_m[uf]
            range_l = bounds.domain.range_l

            if len(range_l) == 0:
                # An empty bound on an *unconstrained* field. Reachable only via a
                # declared domain that intersects its field's width range to
                # nothing (e.g. domain=(300,400) on a u8) -- width ranges are never
                # empty on their own. There is no value to draw, and no solver runs
                # for this field, so report the UNSAT here rather than drawing
                # garbage from a degenerate range.
                raise SolveFailure(
                    "solve failure",
                    "Field %s has an empty domain: its declared domain does not "
                    "intersect its %d-bit%s value range"
                    % (uf.fullname, uf.width, "" if uf.is_signed else " unsigned"))

            if len(range_l) == 1:
                # Single (likely domain-based) range
                uf.set_val(
                    self.randstate.draw(range_l[0][0], range_l[0][1]))
            else:
                uf.set_val(self._draw_multi_range(range_l))

            # Lock so we don't overwrite
            uf.set_used_rand(False)
        PT.add("unconstrained_draw", _t)

        # ---- Whole-problem merged fast path (dv-solve, plan-cached) ----
        # Solve every independent RandSet in one native problem and finalize the
        # fields, skipping the per-RandSet solve/dispose loop. Only taken when the
        # back-end supports it and every RandSet is mergeable (the back-end returns
        # False otherwise); on success we're done, else fall through unchanged.
        if (plan is not None and _MERGE_ENABLED
                and len(ri.randsets()) > 0
                and getattr(self.backend, "solve_merged", None) is not None):
            randsets = ri.randsets()
            try:
                merged_ok = self.backend.solve_merged(
                    randsets, bound_m, self.randstate, plan)
            except SolveFailure:
                # Authoritative UNSAT from the merged solve: dispose + re-raise,
                # matching the per-RandSet failure path.
                for ars in randsets:
                    for f in ars.all_fields():
                        f.dispose()
                if self.solve_fail_debug > 0:
                    raise SolveFailure(
                        "solve failure", self.create_diagnostics(randsets))
                raise SolveFailure(
                    "solve failure",
                    "Solve failure: set 'solve_fail_debug=1' for more details")
            if merged_ok:
                # Finalize every field (write-back already done by solve_merged).
                # No per-RandSet dispose/reset: the merged ctx is reused, so the
                # fields never got individual solver vars to tear down.
                _t = PT.now()
                if opt_flags.LAZY_WALKS:
                    # S1.4/C3. Two observations about this loop, which runs once
                    # per *variable* (128x on a 128-element array):
                    #  - `visited` was a fresh list per field. Only
                    #    FieldCompositeModel touches it, and it appends and
                    #    removes symmetrically, so one shared list is equivalent.
                    #  - FieldScalarModel.post_randomize does exactly two things:
                    #    convert `self.var`, and fire `self.rand_if`. On this
                    #    path `var` is always None (see the comment above — the
                    #    merged ctx means fields never got individual solver
                    #    vars), so for the common scalar with no rand_if the
                    #    call is a guaranteed no-op. Test the two attributes
                    #    instead of paying the call.
                    visited = []
                    for rs in randsets:
                        for f in rs.all_fields():
                            if (getattr(f, "var", None) is not None
                                    or f.rand_if is not None):
                                f.post_randomize(visited)
                            if type(f) is FieldScalarModel:
                                # set_used_rand(False, 0) on a scalar reduces to
                                # `is_used_rand = False and (...)` — always plain
                                # False. Exact-type check so any subclass that
                                # overrides the method still gets it.
                                f.is_used_rand = False
                            else:
                                f.set_used_rand(False, 0)
                else:
                    for rs in randsets:
                        for f in rs.all_fields():
                            visited = []
                            f.post_randomize(visited)
                            f.set_used_rand(False, 0)
                PT.add("merged_finalize", _t)
                return

        # Solve each RandSet through the configured back-end. The grouping,
        # unconstrained-field handling above, the SolveFailure diagnostics, and
        # the post_randomize/dispose finalize below stay in the Randomizer; only
        # the per-group "talk to the solver" block lives behind the back-end.
        reset_v = DynamicExprResetVisitor()
        rs_i = 0
        while rs_i < len(ri.randsets()):
            rs = ri.randsets()[rs_i]

            all_fields = rs.all_fields()
            if self.debug > 0:
                print("Pre-Randomize: RandSet[%d]" % rs_i)
                for f in all_fields:
                    if f in bound_m.keys():
                        print("  Field: %s is_rand=%s %s var=%s" % (f.fullname, str(f.is_used_rand), str(bound_m[f].domain.range_l), str(f.var)))
                    else:
                        print("  Field: %s is_rand=%s (unbounded)" % (f.fullname, str(f.is_used_rand)))
                for c in rs.constraints():
                    print("  Constraint: " + self.pretty_printer.do_print(c, show_exp=True, print_values=True))
                for c in rs.soft_constraints():
                    print("  SoftConstraint: " + self.pretty_printer.do_print(c, show_exp=True, print_values=True))

            if self.solve_info is not None:
                self.solve_info.n_cfields += len(all_fields)

            try:
                self._solve_randset(rs, bound_m)
            except SolveFailure:
                # The system doesn't solve. Dispose every field and produce
                # diagnostics (interim: via Boolector) before re-raising.
                active_randsets = []
                for ars in ri.randsets():
                    active_randsets.append(ars)
                    for f in ars.all_fields():
                        f.dispose()

                if self.solve_fail_debug > 0:
                    raise SolveFailure(
                        "solve failure",
                        self.create_diagnostics(active_randsets))
                else:
                    raise SolveFailure(
                        "solve failure",
                        "Solve failure: set 'solve_fail_debug=1' for more details")

            # Finalize the value of the field
            for f in rs.all_fields():
                visited = []
                f.post_randomize(visited)
                f.set_used_rand(False, 0)
                f.dispose() # Get rid of the solver var, since we're done with it
                f.accept(reset_v)
            for c in rs.constraints():
                c.accept(reset_v)
            RandSetDisposeVisitor().dispose(rs)

            if self.debug > 0:
                print("Post-Randomize: RandSet[%d]" % rs_i)
                for f in all_fields:
                    if f in bound_m.keys():
                        print("  Field: %s %s" % (f.fullname, str(f.val.val)))
                    else:
                        print("  Field: %s (unbounded) %s" % (f.fullname, str(f.val.val)))

                for c in rs.constraints():
                    print("  Constraint: " + self.pretty_printer.do_print(c, show_exp=True, print_values=True))
                for c in rs.soft_constraints():
                    print("  SoftConstraint: " + self.pretty_printer.do_print(c, show_exp=True, print_values=True))

            rs_i += 1

        end = int(round(time.time() * 1000))

    def _solve_randset(self, rs, bound_m):
        """Solve one RandSet on the primary back-end, falling back to the next
        available back-end if the primary raises BackendIncomplete (a construct
        it can't yet handle). SolveFailure (UNSAT) is *not* a fallback trigger
        and propagates to the caller. Raises BackendIncomplete if no back-end
        can handle the RandSet."""
        backends = [self.backend] + self.fallback_backends
        last_exc = None
        for i, be in enumerate(backends):
            try:
                be.solve_randset(
                    rs,
                    bound_m,
                    self.randstate,
                    solve_info=self.solve_info,
                    debug=self.debug)
                # Phase E / E1: optionally cross-check the model dv-solve just
                # produced against Boolector (verdict + membership). No-op unless
                # VSC_DVSOLVE_XCHECK is enabled; consumes no randstate.
                if xcheck.is_enabled():
                    xcheck.xcheck_randset(rs, be.name)
                return
            except BackendIncomplete as e:
                last_exc = e
                reason = getattr(e, "reason_code", "incomplete")
                # Strict mode: surface the would-be fallback loudly instead of
                # silently serving it from the fallback back-end (Phase 0). Still
                # tally it (as a hard-fail) so strict-mode runs populate the
                # Phase-E histogram before raising.
                if _NO_FALLBACK:
                    record_fallback(reason, served=False)
                    raise BackendIncomplete(
                        "VSC_DVSOLVE_NO_FALLBACK: back-end '%s' incomplete for "
                        "RandSet (reason=%s): %s" % (be.name, reason, str(e)),
                        reason_code=reason)
                if i + 1 < len(backends):
                    record_fallback(reason, served=True)
                    if self.solve_info is not None:
                        self.solve_info.add_fallback(reason)
                    if self.debug > 0:
                        print("Note: back-end '%s' incomplete for RandSet "
                              "(reason=%s; %s); falling back to '%s'" % (
                                  be.name, reason, str(e), backends[i + 1].name))
                # else: no further back-end to try; loop ends and we re-raise
        record_fallback(getattr(last_exc, "reason_code", "incomplete"),
                        served=False)
        raise BackendIncomplete(
            "No solver back-end could handle this RandSet: %s" % str(last_exc),
            reason_code=getattr(last_exc, "reason_code", "incomplete"))

    def create_diagnostics_1(self, active_randsets) -> str:
        import pyboolector
        from pyboolector import Boolector
        ret = ""

        btor = Boolector()
        btor.Set_opt(pyboolector.BtorOption.BTOR_OPT_INCREMENTAL, True)
        btor.Set_opt(pyboolector.BtorOption.BTOR_OPT_MODEL_GEN, True)
        model_valid = False
        
        diagnostic_constraint_l = [] 
        diagnostic_field_l = []
        
        # First, determine how many randsets are actually failing
        i = 0
        while i < len(active_randsets):
            rs = active_randsets[i]
            for f in rs.all_fields():
                f.build(btor)

            # Assume that we can omit all soft constraints, since they
            # will have already been omitted (?)                
            constraint_l = list(map(lambda c:(c,c.build(btor)), filter(lambda c:not isinstance(c,ConstraintSoftModel), rs.constraints())))
                
            for c in constraint_l:
                btor.Assume(c[1])

            if btor.Sat() != btor.SAT:
                # Save fields and constraints if the randset doesn't 
                # solve on its own
                diagnostic_constraint_l.extend(constraint_l)
                diagnostic_field_l.extend(rs.fields())
                
            i += 1
            

        problem_constraints = []
        solving_constraints = []
        # Okay, now perform a series of solves to identify
        # constraints that are actually a problem
        for c in diagnostic_constraint_l:
            btor.Assume(c[1])
            model_valid = False
            
            if btor.Sat() != btor.SAT:
                # This is a problematic constraint
                # Save it for later
                problem_constraints.append(c[0])
            else:
                # Not a problem. Assert it now
                btor.Assert(c[1])
                solving_constraints.append(c[0])
                model_valid = True
#                problem_constraints.append(c[0])
                
        if btor.Sat() != btor.SAT:
            raise Exception("internal error: system should solve")
        
        # Okay, we now have a constraint system that solves, and
        # a list of constraints that are a problem. We want to 
        # resolve the value of all variables referenced by the 
        # solving constraints so and then display the non-solving
        # constraints. This will (hopefully) help highlight the
        # reason for the failure
        for c in solving_constraints:
            c.accept(RefFieldsPostRandVisitor())

        ret += "Problem Constraints:\n"
        for i,pc in enumerate(problem_constraints):

            ret += "Constraint %d: %s\n" % (i, SourceInfo.toString(pc.srcinfo))
            ret += ModelPrettyPrinter.print(pc, print_values=True)
            ret += ModelPrettyPrinter.print(pc, print_values=False)

        for rs in active_randsets:
            for f in rs.all_fields():
                f.dispose()
            
        return ret

    def create_diagnostics(self, active_randsets) -> str:
        import pyboolector
        from pyboolector import Boolector

        btor = Boolector()
        btor.Set_opt(pyboolector.BtorOption.BTOR_OPT_INCREMENTAL, True)
        btor.Set_opt(pyboolector.BtorOption.BTOR_OPT_MODEL_GEN, True)
        model_valid = False
        
        diagnostic_constraint_l = [] 
        diagnostic_field_l = []
        
        # First, determine how many randsets are actually failing
        i = 0
        while i < len(active_randsets):
            rs = active_randsets[i]
            for f in rs.all_fields():
                f.build(btor)

            # Assume that we can omit all soft constraints, since they
            # will have already been omitted (?)                
            constraint_l = list(map(lambda c:(c,c.build(btor)), filter(lambda c:not isinstance(c,ConstraintSoftModel), rs.constraints())))
                
            for c in constraint_l:
                btor.Assume(c[1])

            if btor.Sat() != btor.SAT:
                # Save fields and constraints if the randset doesn't 
                # solve on its own
                diagnostic_constraint_l.extend(constraint_l)
                diagnostic_field_l.extend(rs.fields())
                
            i += 1
            
        problem_sets = []
        degree = 1
        
        while True:
            init_size = len(diagnostic_constraint_l)
            tmp_l = []

            ret = self._collect_failing_constraints(
                btor, 
                diagnostic_constraint_l,
                0, 
                degree,
                tmp_l,
                problem_sets)
                
            if len(diagnostic_constraint_l) == init_size and degree > 3:
                break
            else:
                degree += 1

        if Randomizer.EN_DEBUG > 0:
            print("%d constraints remaining ; %d problem sets" % (len(diagnostic_constraint_l), len(problem_sets)))

        # Assert the remaining constraints
        for c in diagnostic_constraint_l:
            btor.Assert(c[1])
                
        if btor.Sat() != btor.SAT:
            raise Exception("internal error: system should solve")
        
        # Okay, we now have a constraint system that solves, and
        # a list of constraints that are a problem. We want to 
        # resolve the value of all variables referenced by the 
        # solving constraints so and then display the non-solving
        # constraints. This will (hopefully) help highlight the
        # reason for the failure
        
        ret = ""
        for ps in problem_sets:
            ret += ("Problem Set: %d constraints\n" % len(ps))
            for pc in ps:
                ret += "  %s:\n" % SourceInfo.toString(pc[0].srcinfo)
                ret += "    %s" % ModelPrettyPrinter.print(pc[0], print_values=False)

            pc = []
            for c in ps:
                pc.append(c[0])
            
            lint_r = LintVisitor().lint(
              [],
              pc)
            
            if lint_r != "":
                ret += "Lint Results:\n" + lint_r
                
        for rs in active_randsets:
            for f in rs.all_fields():
                f.dispose()
            
        return ret            
    
    def _collect_failing_constraints(self,
                                     btor,
                                     src_constraint_l,
                                     idx,
                                     max,
                                     tmp_l,
                                     fail_set_l):
        ret = False
        if len(tmp_l) < max:
            i = idx
            while i < len(src_constraint_l):
                tmp_l.append(i)
                ret = self._collect_failing_constraints(
                    btor, src_constraint_l, i+1, max, tmp_l, fail_set_l)
                tmp_l.pop()
                if ret:
                    src_constraint_l.pop(i)
                else:
                    i += 1
        else:
            # Assume full set of collected constraints
            if Randomizer.EN_DEBUG:
                print("Assume: " + str(tmp_l))
            for c in tmp_l:
                btor.Assume(src_constraint_l[c][1])
            if btor.Sat() != btor.SAT:
                # Set failed. Add to fail_set
                fail_s = []
                for ci in tmp_l:
                    fail_s.append(src_constraint_l[ci])
                fail_set_l.append(tuple(fail_s))
                ret = True
                
        return ret

    
    @staticmethod
    def do_randomize(
            randstate,
            srcinfo : SourceInfo,
            field_model_l : List[FieldModel],
            constraint_l : List[ConstraintModel] = None,
            debug=0,
            lint=0,
            solve_fail_debug=0):
        if profile_on():
            solve_info = SolveInfo()
            solve_info.totaltime = time.time()
            randomize_start(srcinfo, field_model_l, constraint_l)
        else:
            solve_info = None
        
        clear_soft_priority = ClearSoftPriorityVisitor()

        # S1.4/C2: mark for the end-of-call override rollback (see below).
        _ov_mark = constraint_override.installs

        _t = PT.now()
        for f in field_model_l:
            f.set_used_rand(True, 0)
        PT.add("set_used_rand", _t)

        if not opt_flags.LAZY_WALKS:
            # Pre-S1.4 placement: clear unconditionally, on every randomize.
            # The kill-switch has to reproduce the old tree exactly, so the walk
            # moves rather than disappearing (see the cold-path branch below).
            _t = PT.now()
            for f in field_model_l:
                clear_soft_priority.clear(f)
            PT.add("clear_soft_pri", _t)

        if debug > 0:
            print("Initial Model:")        
            for fm in field_model_l:
                print("  " + ModelPrettyPrinter.print(fm))
                
        # First, invoke pre_randomize on all elements
        _t = PT.now()
        visited = []
        for fm in field_model_l:
            fm.pre_randomize(visited)
        PT.add("pre_randomize", _t)

        if constraint_l is None:
            constraint_l = []

        if not opt_flags.LAZY_WALKS:
            _t = PT.now()
            for c in constraint_l:
                clear_soft_priority.clear(c)
            PT.add("clear_soft_pri", _t)

        # Resolve the solve back-end once per randomize call (env/programmatic
        # override > configured default).
        backend = select_backend(get_solver_backend())

        # ---- Pre-solve plan cache (Tier A; perf §4) ----
        # For a single static root with no inline constraints (and, once a first
        # build proves it eligible), reuse the cached bound_m + RandInfo and skip
        # VariableBoundVisitor / array expansion / RandInfoBuilder. Those passes
        # are pure functions of structure + referenced non-rand values for an
        # eligible object; the per-RandSet compiled-problem cache (P1) sits below.
        plan_ok = (_PLAN_CACHE_ENABLED
                   and getattr(backend, "name", None) == "dv-solve"
                   and len(constraint_l) == 0
                   and len(field_model_l) == 1)
        root = field_model_l[0] if plan_ok else None
        plan = getattr(root, _PLAN_ATTR, None) if root is not None else None

        if plan is not None and plan.is_fresh():
            # Tier-A hit: reuse the cached plan, skip the pre-solve passes.
            bound_m = plan.bound_m
            ri = plan.ri
            # RandInfoBuilder is skipped on a hit, so nothing re-accumulates soft
            # priorities — restore them from the plan so the relaxation order
            # matches a cold build. (S1.4/C1: the clear that used to run at the
            # top of every randomize() now runs only on the cold path below. On a
            # hit, clear-then-restore was a round trip to the same state; the one
            # difference is a soft constraint in the tree but in no RandSet, which
            # keeps its previous priority instead of being zeroed — it is not
            # given to the solver either way, and a later cold build clears it.)
            plan.restore_soft_priorities()
        else:
            if root is not None:
                setattr(root, _PLAN_ATTR, None)   # drop any stale plan

            # Zero soft priorities before RandInfoBuilder re-accumulates them.
            # Cold path only: see the Tier-A-hit branch above. 7.2 us/solve on a
            # 128-element warm randomize(), for a model with no soft constraints
            # at all.
            if opt_flags.LAZY_WALKS:
                _t = PT.now()
                for f in field_model_l:
                    clear_soft_priority.clear(f)
                for c in constraint_l:
                    clear_soft_priority.clear(c)
                PT.add("clear_soft_pri", _t)

            # Collect all variables (pre-array) and establish bounds
            _t = PT.now()
            bounds_v = VariableBoundVisitor()
            bounds_v.process(field_model_l, constraint_l, False)
            PT.add("bounds_1", _t)

            # When the back-end consumes `dist` natively, expand to membership
            # only (the back-end's own picker handles weighting / zero-weight
            # exclusion); otherwise expand fully for the Boolector swizzler.
            dist_native = bool(getattr(backend, "supports_dist_native", False))

            # Snapshot rangelist / dist state from the SOURCE (pre-expansion)
            # constraints for the plan cache. Array (`foreach`) expansion below
            # *copies* constraints, so a rangelist/dist referenced inside a
            # foreach appears post-expansion only as frozen per-element copies
            # that do NOT reflect a later mutation of the user-facing source
            # object (e.g. `avail.clear(); avail.extend(...)`). Capturing here
            # tracks the mutable source objects, so is_fresh() invalidates the
            # plan when they change. For a non-array model this is identical to
            # collecting post-expansion (no expansion happens).
            _t = PT.now()
            if root is not None:
                _plan_blocks = _collect_constraint_blocks(field_model_l)
                _plan_rangelist_state = _collect_rangelist_state(_plan_blocks)
                _plan_dist_state = _collect_dist_state(_plan_blocks)
            else:
                _plan_blocks = None
                _plan_rangelist_state = None
                _plan_dist_state = None
            PT.add("plan_snapshot", _t)

            # TODO: need to handle inline constraints that impact arrays
            _t = PT.now()
            constraints_len = len(constraint_l)
            for fm in field_model_l:
                constraint_l.extend(ArrayConstraintBuilder.build(
                    fm, bounds_v.bound_m))
                # Now, handle dist constraints
                DistConstraintBuilder.build(randstate, fm, native=dist_native)

            for c in constraint_l:
                constraint_l.extend(ArrayConstraintBuilder.build(
                    c, bounds_v.bound_m))
                # Now, handle dist constraints
                DistConstraintBuilder.build(randstate, c, native=dist_native)

            arrays_expanded = (len(constraint_l) != constraints_len)
            PT.add("array_dist_expand", _t)

            # If we made changes during array remodeling,
            # re-run bounds checking on the updated model.
            #
            # On a back-end that derives bounds natively (dv-solve), skip the
            # expensive constraint-propagation tightening here: populate only
            # declared domains and let the native core re-derive any tightening
            # and enforce membership from the translated constraints. This is
            # ~24% of cold-path time on large array problems. The remaining
            # consumers of bound_m on this path (unconstrained-field assignment,
            # _domain_of) need only declared domains. See
            # doc/notes/dv_solve_native_full_problem_plan.md (Stage 1).
            _t = PT.now()
            derives_bounds = bool(getattr(backend, "derives_bounds", False))
            bounds_v.process(
                field_model_l, constraint_l, declared_only=derives_bounds)
            bound_m = bounds_v.bound_m
            PT.add("bounds_2", _t)

            if debug > 0:
                print("Final Model:")
                for fm in field_model_l:
                    print("  " + ModelPrettyPrinter.print(fm))
                for c in constraint_l:
                    print("  " + ModelPrettyPrinter.print(c, show_exp=True))

            _t = PT.now()
            ri = RandInfoBuilder.build(field_model_l, constraint_l, Randomizer._rng)
            PT.add("randinfo_build", _t)

            # ---- T0: promote solver-free RandSets to the direct draw ----
            # Runs before the plan is built so the promotion is part of what
            # gets cached; the plan signature below uses ri.all_randsets(), so
            # a promoted RandSet's referenced fields/constraints are still
            # tracked and a change still invalidates the cached domain.
            if _T0_ENABLED:
                _t = PT.now()
                bound_m.update(t0_promote(ri))
                PT.add("t0_promote", _t)

            # Cache the plan when the object has no per-call pipeline behavior.
            if root is not None and _plan_eligible(
                    field_model_l, ri, arrays_expanded, dist_native=dist_native):
                # Use the pre-expansion source snapshots (see above): they track
                # the mutable rangelist/dist objects the user can change between
                # calls; block_state uses the same source constraint blocks.
                blocks = _plan_blocks
                rangelist_state = _plan_rangelist_state
                dist_state = _plan_dist_state
                # all rangelists/dist scopes snapshotable
                if rangelist_state is not None and dist_state is not None:
                    # S1.7: only a non-rand field that some constraint actually
                    # *reads* can change the solution, so only those need their
                    # value in the freshness signature. RandSet.add_field is
                    # called by RandInfoBuilder for every field a constraint
                    # references, so the union of all_fields() over the randsets
                    # is exactly that set (verified: a hard constraint over only
                    # non-rand fields still puts them in a randset, so the
                    # const-constraint UNSAT recheck still invalidates).
                    #
                    # Without this, writing *any* non-rand field between solves
                    # invalidates the plan — the config/knob pattern, and a
                    # measured 7.6x cliff (91 195 -> 11 982 solves/sec) for a
                    # field no constraint mentions.
                    #
                    # is_used_rand stays tracked for *every* field either way: a
                    # rand_mode toggle changes the partitioning regardless of
                    # value. `None` means "value not tracked".
                    if opt_flags.NARROW_PLAN_SIG:
                        refd = set()
                        for _rs in ri.all_randsets():
                            refd.update(_rs.all_fields())
                        field_state = [
                            (f, f.is_used_rand,
                             (None if (f.is_used_rand or f not in refd)
                              else int(f.get_val())))
                            for f in bound_m.keys()]
                    else:
                        field_state = [
                            (f, f.is_used_rand,
                             (None if f.is_used_rand else int(f.get_val())))
                            for f in bound_m.keys()]
                    block_state = [(b, b.enabled) for b in blocks]
                    array_state, _ = (_collect_array_state(field_model_l)
                                      if _ARRAY_PLAN_CACHE else ([], False))
                    keepalive = (list(bound_m.keys()), blocks,
                                 list(ri.all_randsets()),
                                 [rlm for rlm, _ in rangelist_state],
                                 [s for s, _ in dist_state],
                                 [fm for fm, _ in array_state])
                    setattr(root, _PLAN_ATTR,
                            _RandPlan(bound_m, ri, field_state, block_state,
                                      rangelist_state, dist_state, keepalive,
                                      array_state=array_state))

        r = Randomizer(
            randstate,
            solve_info=solve_info,
            debug=debug,
            lint=lint,
            solve_fail_debug=solve_fail_debug,
            backend=backend)

        # The whole-problem merged solve reuses a ctx cached on the plan, so it is
        # available whenever this object is plan-cached (hit or freshly built).
        plan_for_merge = getattr(root, _PLAN_ATTR, None) if root is not None else None

        try:
            r.randomize(ri, bound_m, plan=plan_for_merge)
        finally:
            # Rollback any constraints we've replaced for arrays
            if solve_info is not None:
                solve_info.totaltime = int((time.time() - solve_info.totaltime)*1000)
                randomize_done(srcinfo, solve_info)
            # S1.4/C2: nothing to roll back unless *this call* installed an
            # override. The count is maintained by the installer
            # (ConstraintOverrideVisitor.override_constraint) rather than
            # inferred from the model's structure — inference here is exactly how
            # a silent-wrong bug gets written. Only the cold path installs
            # overrides (array/dist expansion), so a warm randomize() skips a
            # full-tree walk that provably finds nothing.
            if (not opt_flags.LAZY_WALKS
                    or constraint_override.installs != _ov_mark):
                _t = PT.now()
                for fm in field_model_l:
                    ConstraintOverrideRollbackVisitor.rollback(fm)
                PT.add("rollback", _t)

        _t = PT.now()
        visited = []
        for fm in field_model_l:
            fm.post_randomize(visited)
        PT.add("post_randomize", _t)
        
        
        # Process constraints to identify variable/constraint sets
        
