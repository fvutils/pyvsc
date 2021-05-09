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


import random
import sys
import time
from typing import List, Dict

from pyboolector import Boolector, BoolectorNode
import pyboolector
from vsc.constraints import constraint
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
from vsc.model.rand_set_node_builder import RandSetNodeBuilder
from vsc.model.rand_set_dispose_visitor import RandSetDisposeVisitor
from vsc.model.retarget_indexed_coverpoint_target import RetargetIndexedCoverpointTarget
from vsc.model.coverpoint_cross_model import CoverpointCrossModel
from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.expr_in_model import ExprInModel
from vsc.model.constraint_block_model import ConstraintBlockModel


class Randomizer(RandIF):
    """Implements the core randomization algorithm"""
    
    def __init__(self, debug=0):
        self.pretty_printer = ModelPrettyPrinter()
        self.debug = debug
    
    _state_p = [0,1]
    _rng = None
    
    def randomize(self, ri : RandInfo, bound_m : Dict[FieldModel,VariableBoundModel]):
        """Randomize the variables and constraints in a RandInfo collection"""
        

        if self.debug > 0:
            for rs in ri.randsets():
                print("RandSet")
                for f in rs.all_fields():
                    if f in bound_m.keys():
                        print("  Field: " + f.fullname + " " + str(bound_m[f].domain.range_l))
                for c in rs.constraints():
                    print("  Constraint: " + self.pretty_printer.do_print(c, show_exp=True))
            for uf in ri.unconstrained():
                print("Unconstrained: " + uf.name)
               
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
                    self.randint(range_l[0][0], range_l[0][1]))
            else:
                # Most likely an enumerated type
                # TODO: are there any cases where these could be ranges?
                idx = self.randint(0, len(range_l)-1)
                uf.set_val(range_l[idx][0])                
                
            # Lock so we don't overwrite
            uf.set_used_rand(False)

        rs_i = 0
        start_rs_i = 0
        max_fields = 20
        while rs_i < len(ri.randsets()):        
            btor = Boolector()
            self.btor = btor
            btor.Set_opt(pyboolector.BTOR_OPT_INCREMENTAL, True)
            btor.Set_opt(pyboolector.BTOR_OPT_MODEL_GEN, True)
            
            start_rs_i = rs_i

            constraint_l = []
            # Collect up to max_fields fields to randomize at a time
            n_fields = 0
            while rs_i < len(ri.randsets()):
                rs = ri.randsets()[rs_i]
                
                rs_node_builder = RandSetNodeBuilder(btor)

                all_fields = rs.all_fields()
                if self.debug > 0:
                    print("Pre-Randomize: RandSet")
                    for f in all_fields:
                        if f in bound_m.keys():
                            print("  Field: " + f.fullname + " " + str(bound_m[f].domain.range_l))
                    for c in rs.constraints():
                        print("  Constraint: " + self.pretty_printer.do_print(c, show_exp=True, print_values=True))

                rs_node_builder.build(rs)
                n_fields += len(all_fields)
                
                constraint_l.extend(list(map(lambda c:(c,c.build(btor),isinstance(c,ConstraintSoftModel)), rs.constraints())))
                
                rs_i += 1
                if n_fields > max_fields or rs.order != -1:
                    break
                
            for c in constraint_l:
                try:
                    btor.Assume(c[1])
                except Exception as e:
                    from ..visitors.model_pretty_printer import ModelPrettyPrinter
                    print("Exception: " + ModelPrettyPrinter.print(c[0]))
                    raise e
                
            soft_node_l = list(map(lambda c:c[1], filter(lambda c:c[2], constraint_l)))
            node_l = list(map(lambda c:c[1], filter(lambda c:not c[2], constraint_l)))

            # Perform an initial solve to establish correctness
            if btor.Sat() != btor.SAT:
                
                if len(soft_node_l) > 0:
                    # Try one more time before giving up
                    for i,f in enumerate(soft_node_l):
                        if btor.Failed(f):
                            soft_node_l[i] = None
                        
                    # Add back the hard-constraint nodes and soft-constraints that
                    # didn't fail                        
#                    for n in filter(lambda n:n is not None, node_l+soft_node_l):
                    for n in filter(lambda n:n is not None, node_l):
                        btor.Assume(n)
                        
                    for n in filter(lambda n:n is not None, soft_node_l):
                        btor.Assume(n)

                    # If we fail again, then we truly have a problem
                    if btor.Sat() != btor.SAT:
                    
                        # Ensure we clean up
#                        active_randsets = []
#                        x=start_rs_i
#                        while x < rs_i:
#                            rs = ri.randsets()[x]
#                            active_randsets.append(rs)
#                            for f in rs.all_fields():
#                                f.dispose()
#                            x += 1
                        active_randsets = []
                        for rs in ri.randsets():
                            active_randsets.append(rs)
                            for f in rs.all_fields():
                                f.dispose()
                            raise SolveFailure(
                                "solve failure",
                                self.create_diagnostics(active_randsets))

#                        raise SolveFailure(
#                            "solve failure", 
#                            self.create_diagnostics(active_randsets))
                    else:
                        # Still need to convert assumptions to assertions
                        for n in filter(lambda n:n is not None, node_l+soft_node_l):
                            btor.Assert(n)
                else:
#                    print("Failed constraints:")
#                    i=1
#                    for c in constraint_l:
#                        if btor.Failed(c[1]):
#                            print("[" + str(i) + "]: " + self.pretty_printer.do_print(c[0], False))
#                            print("[" + str(i) + "]: " + self.pretty_printer.do_print(c[0], True))
#                            i+=1
                            
                    # Ensure we clean up
                    active_randsets = []
                    for rs in ri.randsets():
                        active_randsets.append(rs)
                        for f in rs.all_fields():
                            f.dispose()
                    raise SolveFailure(
                        "solve failure",
                        self.create_diagnostics(active_randsets))
            else:
                # Still need to convert assumptions to assertions
                btor.Assert(*(node_l+soft_node_l))


            self.swizzle_randvars(btor, ri, start_rs_i, rs_i, bound_m)

        # Finalize the value of the field
            x = start_rs_i
            reset_v = DynamicExprResetVisitor()
            while x < rs_i:
                rs = ri.randsets()[x]
                for f in rs.all_fields():
                    f.post_randomize()
                    f.set_used_rand(False, 0)
                    f.dispose() # Get rid of the solver var, since we're done with it
                    f.accept(reset_v)
#                for f in rs.nontarget_field_s:
#                    f.dispose()
                for c in rs.constraints():
                    c.accept(reset_v)
                RandSetDisposeVisitor().dispose(rs)
                x += 1
                
                
        end = int(round(time.time() * 1000))


                    
    def swizzle_randvars(self, 
                btor     : Boolector, 
                ri       : RandInfo,
                start_rs : int,
                end_rs   : int,
                bound_m  : Dict[FieldModel,VariableBoundModel]):

        # TODO: we must ignore fields that are otherwise being controlled
        if self.debug > 0:
            print("--> swizzle_randvars")

        rand_node_l = []
        rand_e_l = []
        x=start_rs
        while x < end_rs:
            # For each random variable, select a partition with it's known 
            # domain and add the corresponding constraint
            rs = ri.randsets()[x]
            
            field_l = rs.rand_fields()
            
            if self.debug > 0:
                print("  " + str(len(field_l)) + " fields in randset")
            if len(field_l) == 1:
                # Go ahead and pick values in the domain, since there 
                # are no other constraints
                f = field_l[0]
                if f in bound_m.keys():
                    f_bound = bound_m[f]
                    if not f_bound.isEmpty():
                        e = self.create_rand_domain_constraint(f, f_bound)
                        if e is not None:
                            n = e.build(btor)
                            rand_node_l.append(n)
                            rand_e_l.append(e)
            elif len(field_l) > 0:
                field_idx = self.randint(0, len(field_l)-1)
                f = field_l[field_idx]
                if self.debug > 0:
                    print("Swizzling field " + f.name)
                if f in bound_m.keys():
                    f_bound = bound_m[f]
                 
                    if not f_bound.isEmpty():
                        e = self.create_rand_domain_constraint(f, f_bound)
                        if e is not None:
                            n = e.build(btor)
                            rand_node_l.append(n)
                            rand_e_l.append(e)
#                                btor.Assume(n)
                    else:
                        # It's always possible that this value is already fixed.
                        # Just ignore.
#                            rand_node_l.append(None)
                        pass
                else:
                    if self.debug > 0:
                        print("Note: no bounds found for field " + f.name)
            x += 1
            
        if len(rand_node_l) > 0:            
            btor.Assume(*rand_node_l)
#            btor.Assert(*rand_node_l)
     
            if btor.Sat() != btor.SAT:
                # Remove any failing assumptions
                
                if self.debug > 0:
                    print("Randomization constraint failed")
 
                n_failed = 0
                for i,n in enumerate(rand_node_l):
                    if n is not None and btor.Failed(n):
                        rand_node_l[i] = None
                        n_failed += 1

                # Sanity check                
                if n_failed == 0:
                    for e in rand_e_l:
                        print("Constraint: " + ModelPrettyPrinter.print(e))
                    raise Exception("UNSAT reported, but no failing assertions")
# 
                # Re-apply the constraints that succeeded
                btor.Assert(*filter(lambda n:n is not None, rand_node_l))
                if btor.Sat() != btor.SAT:
                    raise Exception("failed to add in randomization (2)")
        else:
            if btor.Sat() != btor.SAT:
                raise Exception("failed to add in randomization")
            
        if self.debug > 0:
            print("<-- swizzle_randvars")
                        
    def create_rand_domain_constraint(self, 
                f : FieldScalarModel, 
                bound_m : VariableBoundModel)->ExprModel:
        e = None
        range_l = bound_m.domain.range_l
        range_idx = self.randint(0, len(range_l)-1)
        range = range_l[range_idx]
        domain = range[1]-range[0]
        
        if self.debug > 0:
            print("create_rand_domain_constraint: " + f.name + " range_idx=" + str(range_idx) + " range=" + str(range))
        if domain > 64:
            r_type = self.randint(0, 3)
            single_val = self.randint(range[0], range[1])
                
            if r_type >= 0 and r_type <= 2: # range
                # Pretty simple. Partition and randomize
                bin_sz_h = 1 if int(domain/128) == 0 else int(domain/128)

                if r_type == 0:                
                    # Center value in bin
                    if single_val+bin_sz_h > range[1]:
                        max = range[1]
                        min = range[1]-2*bin_sz_h
                    elif single_val-bin_sz_h < range[0]:
                        max = range[0]+2*bin_sz_h
                        min = range[0]
                    else:
                        max = single_val+bin_sz_h
                        min = single_val-bin_sz_h
                elif r_type == 1:
                    # Bin starts at value
                    if single_val+2*bin_sz_h > range[1]:
                        max = range[1]
                        min = range[1]-2*bin_sz_h
                    elif single_val-2*bin_sz_h < range[0]:
                        max = range[0]+2*bin_sz_h
                        min = range[0]
                    else:
                        max = single_val+2*bin_sz_h
                        min = single_val
                elif r_type == 2:
                    # Bin ends at value
                    if single_val+2*bin_sz_h > range[1]:
                        max = range[1]
                        min = range[1]-2*bin_sz_h
                    elif single_val-2*bin_sz_h < range[0]:
                        max = range[0]+2*bin_sz_h
                        min = range[0]
                    else:
                        max = single_val
                        min = single_val-2*bin_sz_h
                 
                e = ExprBinModel(
                    ExprBinModel(
                        ExprFieldRefModel(f),
                        BinExprType.Ge,
                        ExprLiteralModel(
                            min,
                            f.is_signed, 
                            f.width)
                    ),
                    BinExprType.And,
                    ExprBinModel(
                        ExprFieldRefModel(f),
                        BinExprType.Le,
                        ExprLiteralModel(
                            max,
                            f.is_signed, 
                            f.width)
                    )
                )
            elif r_type == 3: # Single value
                e = ExprBinModel(
                        ExprFieldRefModel(f),
                        BinExprType.Eq,
                        ExprLiteralModel(single_val, f.is_signed, f.width))
        else:
            val = self.randint(range[0], range[1])
            e = ExprBinModel(
                ExprFieldRefModel(f),
                BinExprType.Eq,
                ExprLiteralModel(val, f.is_signed, f.width))

        return e
    
    def randint(self, low, high):
        if low == high:
            return low
        else:
            if low > high:
                tmp = low
                low = high
                high = tmp

            if (high-low) <= 100:
                return low+int(random.randint(0,10000)%(high-low+1))
            else:                                
                return random.randint(low, high)
    
    def randbits(self, nbits):
#        if Randomizer._rng is None:
#            Randomizer._rng = random.Random(random.randrange(sys.maxsize))
#        return Randomizer._rng.randint(0, (1<<nbits)-1)
        return random.randint(0, (1<<nbits)-1)
    
    def sample(self, s, k):
        return random.sample(s, k)

    @staticmethod            
    def _next():
#        if Randomizer._rng is None:
#            Randomizer._rng = random.Random(random.randrange(sys.maxsize))
#        ret = Randomizer._rng.randint(0, 0xFFFFFFFF)
        ret = random.randint(0, 0xFFFFFFFF)
#         ret = (Randomizer._state_p[0] + Randomizer._state_p[1]) & 0xFFFFFFFF
#         Randomizer._state_p[1] ^= Randomizer._state_p[0]
#         Randomizer._state_p[0] = (((Randomizer._state_p[0] << 55) | (Randomizer._state_p[0] >> 9))
#             ^ Randomizer._state_p[1] ^ (Randomizer._state_p[1] << 14))
#         Randomizer._state_p[1] = (Randomizer._state_p[1] << 36) | (Randomizer._state_p[1] >> 28)
        
        return ret

    def create_diagnostics(self, active_randsets) -> str:
        ret = ""
        
        btor = Boolector()
        btor.Set_opt(pyboolector.BTOR_OPT_INCREMENTAL, True)
        btor.Set_opt(pyboolector.BTOR_OPT_MODEL_GEN, True)
        
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
            
            if btor.Sat() != btor.SAT:
                # This is a problematic constraint
                # Save it for later
                problem_constraints.append(c[0])
            else:
                # Not a problem. Assert it now
                btor.Assert(c[1])
                solving_constraints.append(c[0])
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

            ret += "Constraint " + str(i+1) + ":\n"
            ret += ModelPrettyPrinter.print(pc, print_values=True)
            ret += ModelPrettyPrinter.print(pc, print_values=False)

        for rs in active_randsets:
            for f in rs.all_fields():
                f.dispose()
            
        return ret
            
        
    @staticmethod
    def do_randomize(
            field_model_l : List[FieldModel],
            constraint_l : List[ConstraintModel] = None,
            cg=None,
            debug=0):
        # All fields passed to do_randomize are treated
        # as randomizable
#        if Randomizer._rng is None:
#            Randomizer._rng = random.Random(random.randrange(sys.maxsize))
#        seed = Randomizer._rng.randint(0, (1 << 64)-1)
        seed = random.randint(0, (1<<64)-1)
        
        for f in field_model_l:
            f.set_used_rand(True, 0)
           
        if debug > 0: 
            print("Initial Model:")        
            for fm in field_model_l:
                print("  " + ModelPrettyPrinter.print(fm))
                
        # First, invoke pre_randomize on all elements
        for fm in field_model_l:
            fm.pre_randomize()
            
        if constraint_l is None:
            constraint_l = []
            
        r = Randomizer(debug=debug)
        
        # If a covergroup was provided with unmet goals,
        # add in some constraints to steer things
        if cg is not None:
            candidate_l = []
            
            for cp in cg.coverpoint_l:
                if cp.get_n_unhit_bins() > 0:
                    candidate_l.append(cp)
                    
#            for cr in cg.cross_l:
#                if cr.get_n_unhit_bins() > 0:
#                    candidate_l.append(cr)

            if len(candidate_l) > 0:                    
#                candidate_i = int(r.randint(0, 10000) % len(candidate_l))
                candidate_i = r.randint(0, len(candidate_l)-1)
                candidate = candidate_l[candidate_i]

                if isinstance(candidate, CoverpointCrossModel):
                    pass
                    # Actually, have a series of target expressions and bin values
                else:                
                    bin_i = candidate.select_unhit_bin(r)
                    target_e = RetargetIndexedCoverpointTarget(
                        cg, field_model_l[0]).retarget(candidate.target)
                    rl = candidate.get_bin_rangelist(bin_i)
                    constraint_l.append(ConstraintBlockModel("__bias_c", [
                        ConstraintSoftModel(
                            ExprInModel(
                                target_e, 
                                rl))]))

        # Collect all variables (pre-array) and establish bounds            
        bounds_v = VariableBoundVisitor()
        bounds_v.process(field_model_l, constraint_l, False)
        

        # TODO: need to handle inline constraints that impact arrays
        constraints_len = len(constraint_l)
        for fm in field_model_l:
            constraint_l.extend(ArrayConstraintBuilder.build(
                fm, bounds_v.bound_m))
            # Now, handle dist constraints
            DistConstraintBuilder.build(seed, fm)
            
        for c in constraint_l:
            constraint_l.extend(ArrayConstraintBuilder.build(
                c, bounds_v.bound_m))
            # Now, handle dist constraints
            DistConstraintBuilder.build(seed, c)
            
        # If we made changes during array remodeling,
        # re-run bounds checking on the updated model
#        if len(constraint_l) != constraints_len:
        bounds_v.process(field_model_l, constraint_l)

        if debug > 0:
            print("Final Model:")        
            for fm in field_model_l:
                print("  " + ModelPrettyPrinter.print(fm))
            for c in constraint_l:
                print("  " + ModelPrettyPrinter.print(c, show_exp=True))
            
        ri = RandInfoBuilder.build(field_model_l, constraint_l, Randomizer._rng)
        try:
            r.randomize(ri, bounds_v.bound_m)
        finally:
            # Rollback any constraints we've replaced for arrays
            for fm in field_model_l:
                ConstraintOverrideRollbackVisitor.rollback(fm)
        
        for fm in field_model_l:
            fm.post_randomize()
            
        # Process constraints to identify variable/constraint sets
        
