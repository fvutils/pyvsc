from vsc.model.fieldref_visitor import FieldrefVisitor
from vsc.model.constraint_builder_visitor import ConstraintBuilderVisitor
from random import Random
from vsc.model.field_builder_visitor import FieldBuilderVisitor
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.bin_expr_type import BinExprType
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel

#   Copyright 2019 Matthew Ballance
#   All Rights Reserved Worldwide
#
#   Licensed under the Apache License, Version 2.0 (the
#   "License"); you may not use this file except in
#   compliance with the License.  You may obtain a copy of
#   the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in
#   writing, software distributed under the License is
#   distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
#   CONDITIONS OF ANY KIND, either express or implied.  See
#   the License for the specific language governing
#   permissions and limitations under the License.

'''
Created on Jul 23, 2019

@author: ballance
'''

import pyboolector
from pyboolector import Boolector
from vsc.model.composite_field_model import CompositeFieldModel


class RandObjModel(CompositeFieldModel):
    
    def __init__(self, facade_obj):
        super().__init__(facade_obj, None, True)
        self.is_elab = False;
        self.seed = 1
        self.rand = Random(self.seed)
        self.ref_fields_s = set()
        self.unref_fields_s = set()
        self.level = 0
        self.step = 0
        self.is_init = False

    def elab(self):
        if self.is_elab:
            return
        
        self.is_elab = True
        
        
    def _next(self):
        ret = self.rand.randrange(0, 0xFFFFFFFF)
        return ret

    def do_randomize(self, extra_constraint_l=[]):
        ret = False
        self.pre_randomize()
        
        if not self.is_init:
            # Do a bit of initial work 
            FieldrefVisitor.find(self, self.ref_fields_s, self.unref_fields_s)
            self.is_init = True

        extra_constraint_ref_s = set()
        
        if len(extra_constraint_l) > 0:
            FieldrefVisitor.find(self, extra_constraint_ref_s, None)

        while True:        
            if self.step == 0:
                # Each randomization epoch gets its own Boolector instance
                self.btor = Boolector()
                self.btor.Set_opt(pyboolector.BTOR_OPT_INCREMENTAL, True)
                self.btor.Set_opt(pyboolector.BTOR_OPT_MODEL_GEN, True)
                
                # Build a Boolector representation for each field
                FieldBuilderVisitor.build(self, self.btor)

                # Build and add base constraints
                ConstraintBuilderVisitor.build(self, self.btor)
        
                if self.btor.Sat() != self.btor.SAT:
                    print("Error: base constraints are invalid")
                    break

            if len(extra_constraint_l) > 0: 
                self.btor.Push()
            
                # Build and add inline constraints    
                for ic in extra_constraint_l:
                    ConstraintBuilderVisitor.build(ic, self.btor)
            
                if self.btor.Sat() != self.btor.SAT:
                    print("Error: inline constraints are invalid")
                    break
                
            if self.step == 0:
                # Establish some initial random values
                expr_n_terms = self.mk_rand_c(self.ref_fields_s, self.unref_fields_s)
        
                expr = expr_n_terms[0]
                n_terms = expr_n_terms[1]
        
                # Minimize the equation. This will result
                # in a new frame on the solver stack
                min_v = self.optimize_rand_c(expr, 0, n_terms)
                print("Setup initial random result: min_v=" + str(min_v) + " n_terms=" + str(n_terms))
                ret = True
                break
            else:
                self.btor.Push()
                
                unref_fields_s = self.unref_fields_s.copy()
                for ref_f in extra_constraint_ref_s:
                    if ref_f in unref_fields_s:
                        unref_fields_s.remove(ref_f)
                
                ref_fields_l = list(self.ref_fields_s)
                    
                if len(ref_fields_l) <= 4:
                    n_swizzle = len(ref_fields_l)
                else:
                    n_swizzle = int(len(ref_fields_l)/4)
                    
                # Change all the unreferenced fields
                for f in unref_fields_s:
                    e = ExprBinModel(
                        ExprFieldRefModel(f),
                        BinExprType.Eq,
                        ExprLiteralModel((self._next() & (1 << f.width())-1), False, f.width())
                    )
#                     e = ExprBinModel(
#                         ExprFieldRefModel(f),
#                         BinExprType.Ne,
#                         ExprLiteralModel(f.f.val, False, f.width())
#                     )
                        
                    self.btor.Assert(e.build(self.btor))
                    
                for i in range(n_swizzle):
                    f = ref_fields_l.pop(self._next()%len(ref_fields_l))

                    e = ExprBinModel(
                        ExprFieldRefModel(f),
                        BinExprType.Ne,
                        ExprLiteralModel(f.f.val, False, f.width())
                    )
                        
                    self.btor.Assert(e.build(self.btor))
                    
                if self.btor.Sat() != self.btor.SAT:
                    print("Error: swizzled constraints are invalid")
                    # Go back to the beginning
                    self.step = 0
                else:
                    ret = True
                    break
                
        if ret:        
            # Capture assigned values
            self.post_randomize()
            
            # Pop the randomization context
            self.btor.Pop()
            
            # Move to the next step in this epoch
            if self.step > 100:
                self.step = 0
            else:
                self.step += 1

        # Remove the inline constraints            
        if len(extra_constraint_l) > 0: 
            self.btor.Pop()
        
        return ret

    def mk_rand_c(self, ref_s, unref_s):
        n_terms = 0
        expr = None
        
        all_rand_fields = []
        for f in list(ref_s) + list(unref_s):
            if f.is_rand:
                all_rand_fields.append(f)
                
        print("There are " + str(len(all_rand_fields)) + " rand fields")
        
        if len(all_rand_fields) <= 4:
            n_swizzle_fields = len(all_rand_fields)
        else:
            n_swizzle_fields = int(len(all_rand_fields)/4)
        
        for i in range(n_swizzle_fields):
            f = all_rand_fields.pop(self._next() % len(all_rand_fields))

            bit_l = [*range(f.width())]
            n_bits = int(f.width()-1/8)+1
#            n_bits = int(f.width()-1/4)+1
#            n_bits = int(f.width()-1/2)+1
                
            for i in range(n_bits):
                seed = self._next()
                # Get the bit index randomly out the remaining bits
                bit_i = (seed % len(bit_l))
                bit = bit_l.pop(bit_i)
#                    val = ((seed >> 21) & 1)
#                val = (seed & 1)
                val = 1
                # Evaluates to 0 if the constraint is satisfied, and
                # 1 if the constraint cannot be satisfied. This allows
                # us to minimize the number of constraints that cannot 
                # be satisfied
                e = self.btor.Cond(
                    self.btor.Eq(
                        self.btor.Slice(f.var, bit, bit),
                        self.btor.Const(val, 1)),
                    self.btor.Const(0, 32),
                    self.btor.Const(1, 32))
                n_terms += 1
                
                if expr is None:
                    expr = e
                else:
                    expr = self.btor.Add(expr, e)
                    
        return (expr, n_terms)
    
    def optimize_rand_c(self, expr, min_t, max_t):
        ret = -1

        if min_t==max_t:
            mid_point = min_t
        else:                
            mid_point = min_t + int((max_t-min_t+1)/2)
        print("--> optimize_rand_c: min=" + str(min_t) + " mid_point=" +  str(mid_point) + " max=" + str(max_t))
        
        # Push a new constraint scope
        self.btor.Push()
        
        self.btor.Assert(self.btor.Ulte(
            expr, 
            self.btor.Const(mid_point, 32)))
        
        if self.btor.Sat() == self.btor.SAT:
            print("  SAT")
            if mid_point > 0 and min_t != max_t:
                self.btor.Pop()
                # Continue making the range smaller
                sub_r = self.optimize_rand_c(expr, min_t, mid_point-1)
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
            print("  UNSAT")
            self.btor.Pop()
            if mid_point < max_t:
                # Solve failed, so let's explore the upper portion
                ret = self.optimize_rand_c(expr, mid_point+1, max_t)
            else:
                # Dead-end here
                ret = -1
            
        print("<-- optimize_rand_c: ret=" + str(ret))
        
        return ret
        
                
    def accept(self, visitor):
        visitor.visit_rand_obj(self)
        
        