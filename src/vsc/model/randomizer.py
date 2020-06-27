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


from builtins import zip
import random
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
from vsc.model.model_visitor import ModelVisitor
from vsc.model.rand_if import RandIF
from vsc.model.rand_info import RandInfo
from vsc.model.rand_info_builder import RandInfoBuilder
from vsc.model.field_scalar_model import FieldScalarModel
from vsc.visitors.model_pretty_printer import ModelPrettyPrinter
from vsc.visitors.array_constraint_builder import ArrayConstraintBuilder
from vsc.visitors.constraint_override_rollback_visitor import ConstraintOverrideRollbackVisitor
from vsc.visitors.variable_bound_visitor import VariableBoundVisitor
from vsc.model.variable_bound_model import VariableBoundModel


class Randomizer(RandIF):
    """Implements the core randomization algorithm"""
    
    def __init__(self):
        self.pretty_printer = ModelPrettyPrinter()
    
    _state_p = [0,1]
    _rng = random.Random()
    
    
    def randomize(self, ri : RandInfo, bound_m : Dict[FieldModel,VariableBoundModel]):
        """Randomize the variables and constraints in a RandInfo collection"""
        

#         for rs in ri.randsets():
#             print("RandSet")
#             for f in rs.all_fields():
#                 print("  " + f.name + " " + str(bound_m[f].domain.range_l))
#         for uf in ri.unconstrained():
#             print("Unconstrained: " + uf.name)
        
        
        for rs in ri.randsets():
#             print("RandSet:")
#             for f in rs.fields():
#                 print("  Field: " + f.name)
#             for c in rs.constraints():
#                 print("  Constraint: " + ModelPrettyPrinter.print(c))
#             print("Randset: n_fields=" + str(len(rs.fields())))
            btor = Boolector()
            self.btor = btor
            btor.Set_opt(pyboolector.BTOR_OPT_INCREMENTAL, True)
            btor.Set_opt(pyboolector.BTOR_OPT_MODEL_GEN, True)

            try:            
                for f in rs.all_fields():
                    f.build(btor)
            except Exception as e:
                for c in rs.constraints():
                    print("Constraint: " + self.pretty_printer.do_print(c))
                raise e

            constraint_l = list(map(lambda c:(c,c.build(btor),isinstance(c,ConstraintSoftModel)), rs.constraints()))
            
            for c in constraint_l:
                try:
                    btor.Assume(c[1])
                except Exception as e:
                    from ..visitors.model_pretty_printer import ModelPrettyPrinter
                    print("Exception: " + ModelPrettyPrinter.print(c[0]))
                    raise e
                
            soft_node_l = list(map(lambda c:c[1], filter(lambda c:c[2], constraint_l)))
            node_l = list(map(lambda c:c[1], filter(lambda c:not c[2], constraint_l)))
#             soft_node_l : [BoolectorNode] = []
#                 
#             for c in rs.constraints():
#                 try:
#                     n = c.build(btor)
#                     if isinstance(c, ConstraintSoftModel):
#                         soft_node_l.append(n)
#                     else:
#                         node_l.append(n)
# #                    btor.Assert(c.build(btor))
#                     btor.Assume(n)
#                 except Exception as e:
#                     print("Error: The following constraint failed:\n" + str(c))
#                     raise e
                        
            
            # Perform an initial solve to establish correctness
            if btor.Sat() != btor.SAT:
                
                if len(soft_node_l) > 0:
                
                    # Try one more time before giving up
                    for i,f in enumerate(btor.Failed(*soft_node_l)):
                        if f:
                            soft_node_l[i] = None
                        
                    # Add back the hard-constraint nodes and soft-constraints that
                    # didn't fail                        
                    for n in filter(lambda n:n is not None, node_l+soft_node_l):
                        btor.Assume(n)

                    # If we fail again, then we truly have a problem
                    if btor.Sat() != btor.SAT:
                    
                        # Ensure we clean up
                        for f in rs.all_fields():
                            f.dispose()

                        raise Exception("solve failure")
                    else:
                        # Still need to convert assumptions to assertions
                        for n in filter(lambda n:n is not None, node_l+soft_node_l):
                            btor.Assert(n)
                else:
                    print("Failed constraints:")
                    i=1
                    for c in constraint_l:
                        if btor.Failed(c[1]):
                            print("[" + str(i) + "]: " + self.pretty_printer.do_print(c[0], False))
                            print("[" + str(i) + "]: " + self.pretty_printer.do_print(c[0], True))
                            i+=1
                            
                    # Ensure we clean up
                    for f in rs.all_fields():
                        f.dispose()
                    print("Solve failure")
                    raise Exception("solve failure")
            else:
                # Still need to convert assumptions to assertions
                btor.Assert(*(node_l+soft_node_l))
                

            self.swizzle_randvars(btor, rs, bound_m)

                
            # Finalize the value of the field
            for f in rs.all_fields():
                f.post_randomize()
                f.dispose() # Get rid of the solver var, since we're done with it

        uc_rand = list(filter(lambda f:f.is_used_rand, ri.unconstrained()))
        for uf in uc_rand:
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
            
    def swizzle_randvars(self, 
                btor    : Boolector, 
                rs      : RandInfo,
                bound_m : Dict[FieldModel,VariableBoundModel]):

        # TODO: we must ignore fields that are otherwise being controlled
        
        # For each random variable, select a partition with it's known 
        # domain and add the corresponding constraint
        rand_node_l = []
        
        field_l = list(rs.fields())
        if len(field_l) == 1:
            # Go ahead and pick values in the domain, since there 
            # are no other constraints
            f = field_l[0]
            e = self.create_single_var_domain_constraint(
                field_l[0], bound_m[field_l[0]])
            
            if e is not None:
                n = e.build(btor)
                rand_node_l.append(n)                    
                btor.Assume(n)
        else:
            for f in field_l:
                if f.is_used_rand and f in bound_m.keys():
                    f_bound = bound_m[f]
                 
                    if not f_bound.isEmpty():
                        e = self.create_rand_domain_constraint(f, f_bound)
                        if e is not None:
                            n = e.build(btor)
                            rand_node_l.append(n)                    
                            btor.Assume(n)
                    else:
                        # It's always possible that this value is already fixed.
                        # Just ignore.
                        rand_node_l.append(None)
     
        if btor.Sat() != btor.SAT:
            # Remove any failing assumptions
 
            n_failed = 0
            for i,n in enumerate(rand_node_l):
                if n is not None and btor.Failed(n):
                    rand_node_l[i] = None
                    n_failed += 1
                             
            if btor.Sat() != btor.SAT:
                raise Exception("failed to add in randomization")
            else:
                btor.Assume(*filter(lambda n:n is not None, rand_node_l))
                
                if btor.Sat() != btor.SAT:
                    raise Exception("failed to add in randomization")

    def create_rand_domain_constraint(self, 
                f : FieldScalarModel, 
                bound_m : VariableBoundModel)->ExprModel:
        e = None
        range_l = bound_m.domain.range_l
#        print("create_rand_domain_constraint: " + f.name + " " + str(range_l))
        if len(range_l) == 1:
            domain = range_l[0][1] - range_l[0][0]
            if domain > 64:
                r_type = self.randint(0, 3)
                single_val = self.randint(range_l[0][0], range_l[0][1])
                
                if r_type >= 0 and r_type <= 2: # range
                    # Pretty simple. Partition and randomize
                    bin_sz_h = 1 if int(domain/128) == 0 else int(domain/128)

                    if r_type == 0:                
                        # Center value in bin
                        if single_val+bin_sz_h > range_l[0][1]:
                            max = range_l[0][1]
                            min = range_l[0][1]-2*bin_sz_h
                        elif single_val-bin_sz_h < range_l[0][0]:
                            max = range_l[0][0]+2*bin_sz_h
                            min = range_l[0][0]
                        else:
                            max = single_val+bin_sz_h
                            min = single_val-bin_sz_h
                    elif r_type == 1:
                        # Bin starts at value
                        if single_val+2*bin_sz_h > range_l[0][1]:
                            max = range_l[0][1]
                            min = range_l[0][1]-2*bin_sz_h
                        elif single_val-2*bin_sz_h < range_l[0][0]:
                            max = range_l[0][0]+2*bin_sz_h
                            min = range_l[0][0]
                        else:
                            max = single_val+2*bin_sz_h
                            min = single_val
                    elif r_type == 2:
                        # Bin ends at value
                        if single_val+2*bin_sz_h > range_l[0][1]:
                            max = range_l[0][1]
                            min = range_l[0][1]-2*bin_sz_h
                        elif single_val-2*bin_sz_h < range_l[0][0]:
                            max = range_l[0][0]+2*bin_sz_h
                            min = range_l[0][0]
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
                val = self.randint(0, domain-1)
                e = ExprBinModel(
                    ExprFieldRefModel(f),
                    BinExprType.Eq,
                    ExprLiteralModel(val, f.is_signed, f.width))
        else:
#             domain_bin_ratio = int(len(bound_m.domain.range_l)/len(bound_m.domain_offsets))
#             
#             if domain_bin_ratio <= 1:
#                 # Just pick a single value
#                 print("Should pick single value")
#             else:
#                 #
#                 print("domain_bin_ratio=" + str(domain_bin_ratio))
#                 pass
#             # Multi-range domain
            pass
        
        return e
    
    def create_single_var_domain_constraint(self, 
                    f : FieldScalarModel, 
                    bound_m : VariableBoundModel)->ExprModel:
        range_l = bound_m.domain.range_l
        if len(range_l) == 1:
            val = self.randint(range_l[0][0], range_l[0][1])
            e = ExprBinModel(
                ExprFieldRefModel(f),
                BinExprType.Eq,
                ExprLiteralModel(val, f.is_signed, f.width))
            return e
        else:
#            domain_bin_ratio = int(len(bound_m.domain.range_l)/len(bound_m.domain_offsets))
            domain_bin_ratio = 1
            
            if domain_bin_ratio <= 1:
                # Just pick a single value
                off_val = self.randint(0, bound_m.domain_sz-1)
                target_val = bound_m.offset2value(off_val)
                e = ExprBinModel(
                    ExprFieldRefModel(f),
                    BinExprType.Eq,
                    ExprLiteralModel(target_val, f.is_signed, f.width))
                return e
            else:
                # TODO: For a variable with a small number of bins
                # relative to the domain the cover, it likely makes
                # sense to try to place a range within the bin instead
                # of selecting a single value
                #
                print("domain_bin_ratio=" + str(domain_bin_ratio))
                pass
            
            return None
            
#         gd = f.randgen_data
#         
#         if gd.bag is not None:
#             # Pick out of the bag
#             vi = self.randint(0, len(gd.bag)-1)
#             e = ExprBinModel(
#                 ExprFieldRefModel(f),
#                 BinExprType.Eq,
#                 ExprLiteralModel(gd.bag[vi], f.is_signed, f.width))
#         else:
#             domain = (gd.max-gd.min+1)
#         
#             if domain > 64:
#                 # Bin randomization
#                 bin = self.randint(0, 100)
#                 bin_sz = int(domain/100)
#                 e = ExprBinModel(
#                     ExprBinModel(
#                         ExprFieldRefModel(f),
#                         BinExprType.Ge,
#                         ExprLiteralModel(gd.min+bin_sz*bin, f.is_signed, f.width)
#                     ),
#                     BinExprType.And,
#                     ExprBinModel(
#                         ExprFieldRefModel(f),
#                         BinExprType.Le,
#                         ExprLiteralModel(gd.min+bin_sz*(bin+1)-1, f.is_signed, f.width)
#                         )
#                 )
#             else:
#                 # Select a specific value
#                 off = self.randint(0, domain-1)
#                 e = ExprBinModel(
#                     ExprFieldRefModel(f),
#                     BinExprType.Eq,
#                     ExprLiteralModel(gd.min+off, f.is_signed, f.width)
#                     )        
                

    def calc_domain(self, f : FieldScalarModel, btor : Boolector):
        """Find the reachable bounds of a variable"""
        gd = f.randgen_data
        mid = gd.min + (gd.max-gd.min-1)

        # Find the minimum        
#        while mid > self.min and mid < self.max:
            # 

            
            
        
        pass
        
                
    def swizzle_randvars_slice(self, btor, rs):
        # Form the swizzle expression around bits in the
        # target randset variables. The resulting expression
        # enables us to minimize the deviations from the selected
        # bit values
        rand_node_l = []
        for f in rs.fields():
            val = self.randbits(f.width)
            for i in range(f.width):
                bit_i = ((val >> i) & 1)
                n = btor.Eq(
                    btor.Slice(f.var, i, i),
                    btor.Const(bit_i, 1))
                rand_node_l.append(n)
        btor.Assume(*rand_node_l)
            
        if btor.Sat() != btor.SAT:
            
            # Clear out any failing assumptions
                
            # Try one more time before giving up
            n_failed = 0
            for i,f in enumerate(rand_node_l):
                if btor.Failed(f):
                    rand_node_l[i] = None
                    n_failed += 1
                        
            btor.Assume(*filter(lambda n:n is not None, rand_node_l))
                        
            if btor.Sat() != btor.SAT:
                print("Randomization failed")
                for i,n in enumerate(rand_node_l):
                    if n is not None:
                        if btor.Failed(n):
                            print("Assumption " + str(i) + " failed")
                raise Exception("solve failure") 
        
            
    def minimize(self, expr, min_t, max_t):
        ret = -1

        if min_t==max_t:
            mid_point = min_t
        else:                
            mid_point = min_t + int((max_t-min_t+1)/2)
#        print("--> optimize_rand_c: min=" + str(min_t) + " mid_point=" +  str(mid_point) + " max=" + str(max_t))
        
        # Push a new constraint scope
#        self.btor.Push()
        
        self.btor.Assume(self.btor.Ulte(
            expr, 
            self.btor.Const(mid_point, 32)))
        
        if self.btor.Sat() == self.btor.SAT:
#            print("  SAT")
            if mid_point > 0 and min_t != max_t:
#                self.btor.Pop()
                # Continue making the range smaller
                sub_r = self.minimize(expr, min_t, mid_point-1)
                if sub_r == -1:
                    # re-solve, since this is the best we'll do
                    self.btor.Push()
                    self.btor.Sat()
                    ret = mid_point
                else:
                    # The sub-solved worked out, so take that value
                    ret = sub_r
            else:
                ret = mid_point
        else:
#            print("  UNSAT")
#            self.btor.Pop()
            if mid_point < max_t:
                # Solve failed, so let's explore the upper portion
                ret = self.minimize(expr, mid_point+1, max_t)
            else:
                # Dead-end here
                ret = -1
            
#        print("<-- optimize_rand_c: ret=" + str(ret))
        
        return ret        
    
    def randint(self, low, high):
        return Randomizer._rng.randint(low, high)
    
    def randbits(self, nbits):
        return Randomizer._rng.randint(0, (1<<nbits)-1)

    @staticmethod            
    def _next():
        ret = Randomizer._rng.randint(0, 0xFFFFFFFF)
#         ret = (Randomizer._state_p[0] + Randomizer._state_p[1]) & 0xFFFFFFFF
#         Randomizer._state_p[1] ^= Randomizer._state_p[0]
#         Randomizer._state_p[0] = (((Randomizer._state_p[0] << 55) | (Randomizer._state_p[0] >> 9))
#             ^ Randomizer._state_p[1] ^ (Randomizer._state_p[1] << 14))
#         Randomizer._state_p[1] = (Randomizer._state_p[1] << 36) | (Randomizer._state_p[1] >> 28)
        
        return ret
        
        
    @staticmethod
    def do_randomize(
            field_model_l : List[FieldModel],
            constraint_l : List[ConstraintModel] = None):
        # All fields passed to do_randomize are treated
        # as randomizable
        for f in field_model_l:
            f.set_used_rand(True, 0)
            
        if constraint_l is None:
            constraint_l = []

        # Collect all variables (pre-array) and establish bounds            
        bounds_v = VariableBoundVisitor()
        bounds_v.process(field_model_l, constraint_l, False)

        # TODO: need to handle inline constraints that impact arrays
        constraints_len = len(constraint_l)
        for fm in field_model_l:
            constraint_l.extend(ArrayConstraintBuilder.build(
                fm, bounds_v.bound_m))
            
        # If we made changes during array remodeling,
        # re-run bounds checking on the updated model
#        if len(constraint_l) != constraints_len:
        bounds_v.process(field_model_l, constraint_l)
            
        # First, invoke pre_randomize on all elements
        for fm in field_model_l:
            fm.pre_randomize()

        r = Randomizer()
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
        
