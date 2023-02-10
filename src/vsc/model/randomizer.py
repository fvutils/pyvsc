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


import copy
from dataclasses import dataclass
import sys
import time
from typing import List, Dict

from pyboolector import Boolector, BoolectorNode
import pyboolector
from vsc.constraints import constraint, soft
from vsc.model.bin_expr_type import BinExprType
from vsc.model.constraint_model import ConstraintModel
from vsc.model.constraint_override_model import ConstraintOverrideModel
from vsc.model.constraint_foreach_model import ConstraintForeachModel
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
from vsc.model.rand_set_node_builder import RandSetNodeBuilder
from vsc.model.rand_set_dispose_visitor import RandSetDisposeVisitor
from vsc.visitors.clear_soft_priority_visitor import ClearSoftPriorityVisitor
from vsc.profile import randomize_start, randomize_done, profile_on
from vsc.model.source_info import SourceInfo
from vsc.profile.solve_info import SolveInfo
from vsc.visitors.lint_visitor import LintVisitor
from pip._internal.cli.cmdoptions import src
from vsc.model.solvegroup_swizzler_range import SolveGroupSwizzlerRange
from vsc.model.solvegroup_swizzler_partsel import SolveGroupSwizzlerPartsel
from vsc.impl.ctor import glbl_debug, glbl_solvefail_debug

class Randomizer(RandIF):
    """Implements the core randomization algorithm"""
    
    EN_DEBUG = False

    randomize_cache = {}

    # HACK This is meant to keep constraint object IDs unique by preventing garbage collection
    #      and cycling IDs. Generating unique IDs regardless of lifetimes or better hashing that
    #      explores the entire constraint might be better.
    constraint_keep = []

    def __init__(self, randstate, debug=0, lint=0, solve_fail_debug=0, solve_info=None):
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
            
#        self.swizzler = SolveGroupSwizzlerRange(solve_info)
        self.swizzler = SolveGroupSwizzlerPartsel(randstate, solve_info, debug=self.debug)
        self.btor_cache = {}
        # TODO Reset btor cache after so many uses to circumvent Boolector instance
        #      slowing down as more expressions permanently become part of the model/formula.
        self.btor_cache_uses = 100
    
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

            # TODO We want to re-randomize unconstrained variables when caching. Do we need to lock?
            # Lock so we don't overwrite
            # uf.set_used_rand(False)

        rs_i = 0
        start_rs_i = 0
#        max_fields = 20
        max_fields = 0
        while rs_i < len(ri.randsets()):
            # If missing from cache, initialize/build btor and randset
            # TODO What is going on with max_fields? It would break this
            #      caching setup.
            if rs_i not in self.btor_cache:
                btor = Boolector()
                # TODO Is self.btor used anywhere?
                # self.btor = btor
                btor.Set_opt(pyboolector.BTOR_OPT_INCREMENTAL, True)
                btor.Set_opt(pyboolector.BTOR_OPT_MODEL_GEN, True)
            
                start_rs_i = rs_i

                constraint_l = []
                soft_constraint_l = []
            
                # Collect up to max_fields fields to randomize at a time
                n_fields = 0
                while rs_i < len(ri.randsets()):
                    rs = ri.randsets()[rs_i]

                    rs_node_builder = RandSetNodeBuilder(btor)

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

                    rs_node_builder.build(rs)
                    n_fields += len(all_fields)

                    constraint_l.extend(list(map(lambda c:(c,c.build(btor, False)), rs.constraints())))
                    soft_constraint_l.extend(list(map(lambda c:(c,c.build(btor, True)), rs.soft_constraints())))

                    # Sort the list in descending order so we know which constraints
                    # to prioritize
                    soft_constraint_l.sort(key=lambda c:c[0].priority, reverse=True)

                    # TODO: Is this part of a disabled feature to solve randsets together?
                    # rs_i += 1
                    if n_fields > max_fields or rs.order != -1:
                        break
                    
                for c in constraint_l:
                    try:
                        btor.Assume(c[1])
                    except Exception as e:
                        print("Exception: " + self.pretty_printer.print(c[0]))
                        raise e

                if self.solve_info is not None:
                    self.solve_info.n_sat_calls += 1

                if btor.Sat() != btor.SAT:
                    # If the system doesn't solve with hard constraints added,
                    # then we may as well bail now
                    active_randsets = []
                    for rs in ri.randsets():
                        active_randsets.append(rs)
                        for f in rs.all_fields():
                            f.dispose()

                    if self.solve_fail_debug > 0:
                        raise SolveFailure(
                            "solve failure",
                            self.create_diagnostics(active_randsets))
                    else:
                        raise SolveFailure(
                            "solve failure",
                            "Solve failure: set 'solve_fail_debug=1' for more details")
                else:
                    # Lock down the hard constraints that are confirmed
                    # to be valid
                    for c in constraint_l:
                        btor.Assert(c[1])

                # If there are soft constraints, add these now
                if len(soft_constraint_l) > 0:                
                    for c in soft_constraint_l:
                        try:
                            btor.Assume(c[1])
                        except Exception as e:
                            from ..visitors.model_pretty_printer import ModelPrettyPrinter
                            print("Exception: " + ModelPrettyPrinter.print(c[0]))
                            raise e

                    if self.solve_info is not None:
                        self.solve_info.n_sat_calls += 1                    
                    if btor.Sat() != btor.SAT:
                        # All the soft constraints cannot be satisfied. We'll need to
                        # add them incrementally
                        if self.debug > 0:
                            print("Note: some of the %d soft constraints could not be satisfied" % len(soft_constraint_l))

                        for c in soft_constraint_l:
                            btor.Assume(c[1])

                            if self.solve_info is not None:
                                self.solve_info.n_sat_calls += 1                    
                            if btor.Sat() == btor.SAT:
                                if self.debug > 0:
                                    print("Note: soft constraint %s (%d) passed" % (
                                        self.pretty_printer.print(c[0]), c[0].priority))
                                btor.Assert(c[1])
                            else:
                                if self.debug > 0:
                                    print("Note: soft constraint %s (%d) failed" % (
                                        self.pretty_printer.print(c[0]), c[0].priority))
                    else:
                        # All the soft constraints could be satisfied. Assert them now
                        if self.debug > 0:
                            print("Note: all %d soft constraints could be satisfied" % len(soft_constraint_l))
                        for c in soft_constraint_l:
                            btor.Assert(c[1])

                # Changes made to the randset are covered by the randomization_cache 
                # Cache btor reference for use later
                self.btor_cache[rs_i] = btor
            else:
                # Setup some necessary variables
                start_rs_i = rs_i
                rs = ri.randsets()[rs_i]
                btor = self.btor_cache[rs_i]
                # TODO Is self.btor used anywhere?
                # self.btor = btor
                all_fields = rs.all_fields()

            rs_i += 1

            # TODO Boolector Push()/Pop() do not release orphan expressions/nodes and
            #      cause Sat() calls to slow down and leak memory. Add release feature to PyBoolector?
            btor.Push()

#            btor.Sat()
            x = start_rs_i
            while x < rs_i:
                self.swizzler.swizzle(
                    btor,
                    ri.randsets()[x],
                    bound_m)
                x += 1

            # Finalize the value of the field
            x = start_rs_i
            # TODO What cleanup do we need if caching?
            # reset_v = DynamicExprResetVisitor()
            while x < rs_i:
                rs = ri.randsets()[x]
                for f in rs.all_fields():
                    f: FieldScalarModel = f
                    f.post_randomize()
                    # TODO What does this all do? Do we need to clean up if we're going to reuse this agian?
                    # f.set_used_rand(False, 0)
                    # f.dispose() # Get rid of the solver var, since we're done with it
                    # f.accept(reset_v)
#                for f in rs.nontarget_field_s:
#                    f.dispose()
                # TODO What does this all do? Do we need to clean up if we're going to reuse this agian?
                # for c in rs.constraints():
                #     c.accept(reset_v)
                # TODO What does this all do? Do we need to clean up if we're going to reuse this agian?
                # RandSetDisposeVisitor().dispose(rs)
                
                if self.debug > 0:
                    print("Post-Randomize: RandSet[%d]" % x)
                    for f in all_fields:
                        if f in bound_m.keys():
                            print("  Field: %s %s" % (f.fullname, str(f.val.val)))
                        else:
                            print("  Field: %s (unbounded) %s" % (f.fullname, str(f.val.val)))
                                  
                    for c in rs.constraints():
                        print("  Constraint: " + self.pretty_printer.do_print(c, show_exp=True, print_values=True))
                    for c in rs.soft_constraints():
                        print("  SoftConstraint: " + self.pretty_printer.do_print(c, show_exp=True, print_values=True))
                        
                x += 1

            # TODO Cleanup boolector state. See Push() comment above.
            btor.Pop()
                
        end = int(round(time.time() * 1000))

    def create_diagnostics_1(self, active_randsets) -> str:
        ret = ""
        
        btor = Boolector()
        btor.Set_opt(pyboolector.BTOR_OPT_INCREMENTAL, True)
        btor.Set_opt(pyboolector.BTOR_OPT_MODEL_GEN, True)
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
        
        btor = Boolector()
        btor.Set_opt(pyboolector.BTOR_OPT_INCREMENTAL, True)
        btor.Set_opt(pyboolector.BTOR_OPT_MODEL_GEN, True)
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

        if constraint_l is None:
            constraint_l = []
        
        # HACK Fill out field_l in FieldArrayModels so that look ups work
        # This breaks deepcopy since it'll now have deepcopy references...
        for fm in field_model_l:
            if hasattr(fm, 'field_l'):
                for f in fm.field_l:
                    if hasattr(f, 'field_l'):
                        f.latest_field_l = None

        # The call_hash needs the value of non-rand fields in the pretty printer
        for f in field_model_l:
            f.set_used_rand(True, 0)

        # Generate dist constraints early for generating call hash
        (field_model_l_og, constraint_l_og) = (field_model_l, constraint_l) # copy.deepcopy((field_model_l, constraint_l))
        randstate_copy = copy.deepcopy(randstate)
        for fm in field_model_l_og:
            DistConstraintBuilder.build(randstate_copy, fm)
        for c in constraint_l_og:
            DistConstraintBuilder.build(randstate_copy, c)

        # Create a unique string for this call based on object ids and mode bits
        # Is there more than rand_mode and constraint_mode to cover here?
        # TODO Can we cache the base constraints so that with constraints have a prebuilt
        #      model and such to build off of?
        # call_hash = Randomizer.get_id_call_hash(field_model_l, constraint_l, field_model_l_copy, constraint_l_copy)
        call_hash = Randomizer.get_pretty_call_hash(randstate, field_model_l_og, constraint_l_og)

        for fm in field_model_l_og:
            ConstraintOverrideRollbackVisitor.rollback(fm)

        if call_hash in Randomizer.randomize_cache:
            cache = Randomizer.randomize_cache[call_hash]
            cache.r.btor_cache_uses -= 1
            if cache.r.btor_cache_uses <= 0:
                del Randomizer.randomize_cache[call_hash]

        if call_hash in Randomizer.randomize_cache:
            cache = Randomizer.randomize_cache[call_hash]

            clear_soft_priority = ClearSoftPriorityVisitor()

            # Reset cached field_model_l vars to be rand again
            # TODO This is untested. Are there deepcopy issues here?
            for f in cache.field_model_l:
                f.set_used_rand(True, 0)
                clear_soft_priority.clear(f)

            # First, invoke pre_randomize on all elements
            # TODO This is untested. What happens to pre_randomize() on a deepcopy?
            for fm in cache.field_model_l:
                fm.pre_randomize()

            Randomizer.try_randomize(srcinfo, cache.field_model_l, solve_info, cache.bounds_v, cache.r, cache.ri)
        else:
            # Make copy of field and constraint models, together to keep FieldScalarModels the same
            # TODO The deepcopy() in FieldScalarModel keeps the val reference, is that the best way?
            (field_model_l, constraint_l) = copy.deepcopy((field_model_l, constraint_l))

            clear_soft_priority = ClearSoftPriorityVisitor()
        
            for f in field_model_l:
                f.set_used_rand(True, 0)
                clear_soft_priority.clear(f)

            if debug > 0: 
                print("Initial Model:")        
                for fm in field_model_l:
                    print("  " + ModelPrettyPrinter.print(fm))

            # First, invoke pre_randomize on all elements
            for fm in field_model_l:
                fm.pre_randomize()

            for c in constraint_l:
                clear_soft_priority.clear(c)

            # Collect all variables (pre-array) and establish bounds            
            bounds_v = VariableBoundVisitor()
            bounds_v.process(field_model_l, constraint_l, False)

            # TODO: need to handle inline constraints that impact arrays
            constraints_len = len(constraint_l)
            # TODO dist are handled as soft constraints that caching doesn't recalculate...
            for fm in field_model_l:
                constraint_l.extend(ArrayConstraintBuilder.build(
                    fm, bounds_v.bound_m))
                # Now, handle dist constraints
                # TODO Does this depend on the ArrayConstraintBuilder above?
                DistConstraintBuilder.build(randstate, fm)

            for c in constraint_l:
                constraint_l.extend(ArrayConstraintBuilder.build(
                    c, bounds_v.bound_m))
                # Now, handle dist constraints
                # TODO Does this depend on the ArrayConstraintBuilder above?
                DistConstraintBuilder.build(randstate, c)

            # If we made changes during array remodeling,
            # re-run bounds checking on the updated model
#            if len(constraint_l) != constraints_len:
            bounds_v.process(field_model_l, constraint_l)

            if debug > 0:
                print("Final Model:")        
                for fm in field_model_l:
                    print("  " + ModelPrettyPrinter.print(fm))
                for c in constraint_l:
                    print("  " + ModelPrettyPrinter.print(c, show_exp=True))

#            if lint > 0:
#                LintVisitor().lint(
#                    field_model_l,
#                    constraint_l)

            r = Randomizer(
                randstate,
                solve_info=solve_info,
                debug=debug, 
                lint=lint, 
                solve_fail_debug=solve_fail_debug)
#            if Randomizer._rng is None:
#                Randomizer._rng = random.Random(random.randrange(sys.maxsize))
            ri = RandInfoBuilder.build(field_model_l, constraint_l, Randomizer._rng)

            # TODO Unecessary function refactor? 
            Randomizer.try_randomize(srcinfo, field_model_l, solve_info, bounds_v, r, ri)

            # Cache all interesting variables for later 
            Randomizer.randomize_cache[call_hash] = rand_cache_entry(bounds_v, ri, r, field_model_l, constraint_l)

        # HACK Fill out field_l in FieldArrayModels so that look ups work
        # This breaks deepcopy since it'll now have deepcopy references...
        field_model_l = Randomizer.randomize_cache[call_hash].field_model_l
        for fm_new, fm_og in zip(field_model_l, field_model_l_og):
            if hasattr(fm_og, 'field_l'):
                for f_new, f_og in zip(fm_new.field_l, fm_og.field_l):
                    if hasattr(f_og, 'field_l'):
                        f_og.latest_field_l = f_new.field_l


    @staticmethod
    def get_pretty_call_hash(randstate, field_model_l, constraint_l):
        call_hash = ''
        call_hash += f'{hex(id(randstate))}\n'
        if field_model_l is not None: 
            for fm in field_model_l:
                # TODO This pretty print is an expensive call. Need a better way
                #      to construct a unique ID/hash that doesn't depend on
                #      object lifetimes
                call_hash += ModelPrettyPrinter.print(fm)
                # Each constraint block and whether it's enabled
                if hasattr(fm, 'field_l'):
                    for f in fm.field_l:
                        call_hash += f'{f.fullname}-{f.rand_mode=}\n'
                # Each constraint block and whether it's enabled
                if hasattr(fm, 'constraint_model_l'):
                    for cm in fm.constraint_model_l:
                        call_hash += f'{cm.name}-{cm.enabled=}\n'
                if hasattr(fm, 'constraint_model_l'):
                    for cm in fm.constraint_model_l:
                        # TODO dist constraint hack
                        #      T
                        for c in cm.constraint_l:
                            if isinstance(c, ConstraintOverrideModel):
                                # dist_value = c.new_constraint.constraint_l[-1].expr.rhs.val().toString()
                                # call_hash += f'{cm.name}-{dist_value=}\n'
                                call_hash += f'{hex(id(c.new_constraint))}\n'
                            if isinstance(c, ConstraintForeachModel):
                                for fe_c in c.constraint_l:
                                    if isinstance(fe_c, ConstraintOverrideModel):
                                        call_hash += f'{hex(id(fe_c.new_constraint))}\n'

        if constraint_l is not None: 
            # Each with constraint(block?) and its expressions
            # TODO Is this missing anything? Dynamic expressions? Too aggressive?
            for cm in constraint_l:
                call_hash += ModelPrettyPrinter.print(cm)
                # HACK Place with constraints inside list forever to prevent obj ID reuse
                Randomizer.constraint_keep.append(cm)
                call_hash += f'{hex(id(cm))}-{cm.name}-{cm.enabled=}\n'
                for c in cm.constraint_l:
                    call_hash += f'{hex(id(c))}\n'
                for c in cm.constraint_l:
                    # TODO dist constraint hack
                    if isinstance(c, ConstraintOverrideModel):
                        # dist_value = c.new_constraint.constraint_l[-1].expr.rhs.val().toString()
                        # call_hash += f'{c.name}-{dist_value=}\n'
                        call_hash += f'{hex(id(c.new_constraint))}\n'
                    if isinstance(c, ConstraintForeachModel):
                        for fe_c in c.constraint_l:
                            if isinstance(fe_c, ConstraintOverrideModel):
                                call_hash += f'{hex(id(fe_c.new_constraint))}\n'
        return call_hash

    @staticmethod
    def get_id_call_hash(field_model_l, constraint_l, fml_copy, cl_copy):
        call_hash = ''
        if field_model_l is not None: 
            for fm in field_model_l:
                # Each field and its rand_mode
                # TODO call_hash += f'{hex(id(fm))}-{fm.fullname}\n'
                if hasattr(fm, 'field_l'):
                    for f in fm.field_l:
                        call_hash += f'{hex(id(f))}-{f.fullname}-{f.rand_mode=}\n'
                # Each constraint block and whether it's enabled
                if hasattr(fm, 'constraint_model_l'):
                    for cm in fm.constraint_model_l:
                        call_hash += f'{hex(id(cm))}-{cm.name}-{cm.enabled=}\n'
            for fm in fml_copy:
                # Each constraint block and whether it's enabled
                if hasattr(fm, 'constraint_model_l'):
                    for cm in fm.constraint_model_l:
                        # TODO dist constraint hack
                        for c in cm.constraint_l:
                            if isinstance(c, ConstraintOverrideModel):
                                # dist_value = c.new_constraint.constraint_l[-1].expr.rhs.val().toString()
                                # call_hash += f'{cm.name}-{dist_value=}\n'
                                call_hash += f'{hex(id(c.new_constraint))}\n'
                            if isinstance(c, ConstraintForeachModel):
                                for fe_c in c.constraint_l:
                                    if isinstance(fe_c, ConstraintOverrideModel):
                                        call_hash += f'{hex(id(fe_c.new_constraint))}\n'
        if constraint_l is not None: 
            # Each with constraint(block?) and its expressions
            # TODO Is this missing anything? Dynamic expressions? Too aggressive?
            for cm in constraint_l:
                Randomizer.constraint_keep.append(cm)
                call_hash += f'{hex(id(cm))}-{cm.name}-{cm.enabled=}\n'
                for c in cm.constraint_l:
                    call_hash += f'{hex(id(c))}\n'
            
            for cm in cl_copy:
                for c in cm.constraint_l:
                    # TODO dist constraint hack
                    if isinstance(c, ConstraintOverrideModel):
                        # dist_value = c.new_constraint.constraint_l[-1].expr.rhs.val().toString()
                        # call_hash += f'{c.name}-{dist_value=}\n'
                        call_hash += f'{hex(id(c.new_constraint))}\n'
                    if isinstance(c, ConstraintForeachModel):
                        for fe_c in c.constraint_l:
                            if isinstance(fe_c, ConstraintOverrideModel):
                                call_hash += f'{hex(id(fe_c.new_constraint))}\n'
        return call_hash

    @staticmethod
    def try_randomize(srcinfo, field_model_l, solve_info, bounds_v, r, ri):
        try:
            r.randomize(ri, bounds_v.bound_m)
        finally:
            # Rollback any constraints we've replaced for arrays
            if solve_info is not None:
                solve_info.totaltime = int((time.time() - solve_info.totaltime)*1000)
                randomize_done(srcinfo, solve_info)
            for fm in field_model_l:
                ConstraintOverrideRollbackVisitor.rollback(fm)
        
        for fm in field_model_l:
            fm.post_randomize()
        
        
        # Process constraints to identify variable/constraint sets

@dataclass
class rand_cache_entry:
    bounds_v: VariableBoundVisitor
    ri: RandInfo
    r: Randomizer
    field_model_l: list
    constraint_l: list