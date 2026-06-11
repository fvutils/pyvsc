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
from vsc.visitors.array_constraint_builder import ArrayConstraintBuilder
from vsc.visitors.constraint_override_rollback_visitor import ConstraintOverrideRollbackVisitor
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
from vsc.impl.ctor import glbl_debug, glbl_solvefail_debug, get_solver_backend


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

# Strict no-fallback mode (feature-completeness plan, Phase 0). When set, the
# Randomizer does NOT fall back from the primary back-end to another on
# BackendIncomplete — it re-raises, so any residual dependence on the fallback
# back-end (e.g. Boolector) surfaces loudly in CI. Used to enumerate and
# burn down the remaining defers per phase. Off by default.
_NO_FALLBACK = os.environ.get("VSC_DVSOLVE_NO_FALLBACK", "0") != "0"


class _RandPlan(object):
    """Cached pre-solve plan for one root model object (Tier-A)."""

    __slots__ = ("bound_m", "ri", "field_state", "block_state",
                 "rangelist_state", "dist_state", "_keepalive")

    def __init__(self, bound_m, ri, field_state, block_state, rangelist_state,
                 dist_state, keepalive):
        self.bound_m = bound_m
        self.ri = ri
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

    def is_fresh(self):
        for f, was_rand, val in self.field_state:
            if f.is_used_rand != was_rand:
                return False
            if not was_rand and int(f.get_val()) != val:
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


class _RangelistCollector(ModelVisitor):
    """Collect every ExprRangelistModel reachable from a constraint block."""

    def __init__(self):
        super().__init__()
        self.rangelists = []

    def visit_expr_rangelist(self, r):
        self.rangelists.append(r)
        super().visit_expr_rangelist(r)


def _snapshot_rangelist(rlm):
    """A hashable snapshot of a rangelist's current range bounds, or None if a
    bound can't be evaluated to an int (→ caller treats the object as
    ineligible). `inside` rangelists are the one mutable input to bound_m that
    field_state doesn't capture: the rangelist object is stable but `o.rl.clear()
    / .extend(...)` rebuilds its range literals in place."""
    snap = []
    for item in rlm.rl:
        lhs = getattr(item, "lhs", None)
        rhs = getattr(item, "rhs", None)
        try:
            if lhs is not None and rhs is not None:
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
    plan signature captures. So arrays make an object plan-cache-ineligible."""
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


def _plan_eligible(field_model_l, ri, arrays_expanded, dist_native=False):
    """Tier-A eligibility: no per-call pipeline behavior. (Inline constraints and
    backend gating are checked by the caller.)"""
    if arrays_expanded:
        return False                      # array expansion grew constraint_l
    if _model_has_array(field_model_l):
        return False                      # array overrides / mutable refs
    for fm in field_model_l:
        if type(fm).__name__ == "GeneratorModel":
            return False                  # coverage steering is per-call
    for rs in ri.randsets():
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
    
    _state_p = [0,1]
    _rng = None
    
    def randomize(self, ri : RandInfo, bound_m : Dict[FieldModel,VariableBoundModel]):
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
               
        # Assign values to the unconstrained fields first
        uc_rand = list(filter(lambda f:f.is_used_rand, ri.unconstrained()))
        for uf in uc_rand:
            if self.debug > 0:
                print("Randomizing unconstrained: " + uf.fullname)
            bounds = bound_m[uf]
            range_l = bounds.domain.range_l
            
            if len(range_l) == 1:
                # Single (likely domain-based) range
                uf.set_val(
                    self.randstate.randint(range_l[0][0], range_l[0][1]))
            else:
                # Most likely an enumerated type
                # TODO: are there any cases where these could be ranges?
                idx = self.randstate.randint(0, len(range_l)-1)
                uf.set_val(range_l[idx][0])                
                
            # Lock so we don't overwrite
            uf.set_used_rand(False)

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
                return
            except BackendIncomplete as e:
                last_exc = e
                reason = getattr(e, "reason_code", "incomplete")
                # Strict mode: surface the would-be fallback loudly instead of
                # silently serving it from the fallback back-end (Phase 0).
                if _NO_FALLBACK:
                    raise BackendIncomplete(
                        "VSC_DVSOLVE_NO_FALLBACK: back-end '%s' incomplete for "
                        "RandSet (reason=%s): %s" % (be.name, reason, str(e)),
                        reason_code=reason)
                if i + 1 < len(backends):
                    if self.solve_info is not None:
                        self.solve_info.add_fallback(reason)
                    if self.debug > 0:
                        print("Note: back-end '%s' incomplete for RandSet "
                              "(reason=%s; %s); falling back to '%s'" % (
                                  be.name, reason, str(e), backends[i + 1].name))
                # else: no further back-end to try; loop ends and we re-raise
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
        
        for f in field_model_l:
            f.set_used_rand(True, 0)
            clear_soft_priority.clear(f)
           
        if debug > 0: 
            print("Initial Model:")        
            for fm in field_model_l:
                print("  " + ModelPrettyPrinter.print(fm))
                
        # First, invoke pre_randomize on all elements
        visited = []
        for fm in field_model_l:
            fm.pre_randomize(visited)
            
        if constraint_l is None:
            constraint_l = []

        for c in constraint_l:
            clear_soft_priority.clear(c)

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
        else:
            if root is not None:
                setattr(root, _PLAN_ATTR, None)   # drop any stale plan

            # Collect all variables (pre-array) and establish bounds
            bounds_v = VariableBoundVisitor()
            bounds_v.process(field_model_l, constraint_l, False)

            # When the back-end consumes `dist` natively, expand to membership
            # only (the back-end's own picker handles weighting / zero-weight
            # exclusion); otherwise expand fully for the Boolector swizzler.
            dist_native = bool(getattr(backend, "supports_dist_native", False))

            # TODO: need to handle inline constraints that impact arrays
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

            # If we made changes during array remodeling,
            # re-run bounds checking on the updated model
            bounds_v.process(field_model_l, constraint_l)
            bound_m = bounds_v.bound_m

            if debug > 0:
                print("Final Model:")
                for fm in field_model_l:
                    print("  " + ModelPrettyPrinter.print(fm))
                for c in constraint_l:
                    print("  " + ModelPrettyPrinter.print(c, show_exp=True))

            ri = RandInfoBuilder.build(field_model_l, constraint_l, Randomizer._rng)

            # Cache the plan when the object has no per-call pipeline behavior.
            if root is not None and _plan_eligible(
                    field_model_l, ri, arrays_expanded, dist_native=dist_native):
                blocks = _collect_constraint_blocks(field_model_l)
                rangelist_state = _collect_rangelist_state(blocks)
                dist_state = _collect_dist_state(blocks)
                # all rangelists/dist scopes snapshotable
                if rangelist_state is not None and dist_state is not None:
                    field_state = [
                        (f, f.is_used_rand,
                         (0 if f.is_used_rand else int(f.get_val())))
                        for f in bound_m.keys()]
                    block_state = [(b, b.enabled) for b in blocks]
                    keepalive = (list(bound_m.keys()), blocks,
                                 list(ri.randsets()),
                                 [rlm for rlm, _ in rangelist_state],
                                 [s for s, _ in dist_state])
                    setattr(root, _PLAN_ATTR,
                            _RandPlan(bound_m, ri, field_state, block_state,
                                      rangelist_state, dist_state, keepalive))

        r = Randomizer(
            randstate,
            solve_info=solve_info,
            debug=debug,
            lint=lint,
            solve_fail_debug=solve_fail_debug,
            backend=backend)

        try:
            r.randomize(ri, bound_m)
        finally:
            # Rollback any constraints we've replaced for arrays
            if solve_info is not None:
                solve_info.totaltime = int((time.time() - solve_info.totaltime)*1000)
                randomize_done(srcinfo, solve_info)
            for fm in field_model_l:
                ConstraintOverrideRollbackVisitor.rollback(fm)

        visited = []
        for fm in field_model_l:
            fm.post_randomize(visited)
        
        
        # Process constraints to identify variable/constraint sets
        
