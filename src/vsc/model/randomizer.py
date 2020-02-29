
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

'''
Created on Jan 21, 2020

@author: ballance
'''
from vsc.model.field_model import FieldModel
from vsc.model.constraint_model import ConstraintModel
from vsc.model.model_visitor import ModelVisitor
from vsc.model.rand_info_builder import RandInfoBuilder
from vsc.model.rand_info import RandInfo
from pyboolector import Boolector
from typing import List
import pyboolector
import random

class Randomizer(object):
    """Implements the core randomization algorithm"""
    
    _state_p = [0,1]
    _rng = random.Random()
    
    
    def randomize(self, ri : RandInfo):
        """Randomize the variables and constraints in a RandInfo collection"""
        
        print("Num Randsets: " + str(len(ri.randsets())))
        
        for rs in ri.randsets():
#             print("RandSet:")
#             for f in rs.fields():
#                 print("  Field: " + f.name())
#             for c in rs.constraints():
#                 print("  Constraint: " + str(c))
            print("Randset: n_fields=" + str(len(rs.fields())))
            btor = Boolector()
            self.btor = btor
            btor.Set_opt(pyboolector.BTOR_OPT_INCREMENTAL, True)
            btor.Set_opt(pyboolector.BTOR_OPT_MODEL_GEN, True)
            
            for f in rs.fields():
                f.build(btor)
                
            for c in rs.constraints():
                btor.Assert(c.build(btor))
            
            # Perform an initial solve to establish correctness
            if btor.Sat() != btor.SAT:
                # Ensure we clean up
                for f in rs.fields():
                    f.dispose()
                    
                raise Exception("solve failure")
            
            # Form the swizzle expression around bits in the
            # target randset variables. The resulting expression
            # enables us to minimize the deviations from the selected
            # bit values
#             expr = None
#             n_terms = 0
#             for f in rs.fields():
#  
#                 if f.width() < 8:
#                     bit_n = f.width()
#                 else:
#                     bit_n = int(f.width() / 2)
#                 bit_l = [*range(f.width())]
#                 for i in range(bit_n):
#                     bit_i = self.randint(0, len(bit_l)-1)
#                     bit = bit_l.pop(bit_i)
#  
#                     val = self.randint(0, 1)                    
#                      
#                     e = btor.Cond(
#                         btor.Eq(
#                             btor.Slice(f.var, bit, bit),
#                             btor.Const(val, 1)),
#                         btor.Const(0, 32),
#                         btor.Const(1, 32))
#                     n_terms += 1
#                      
#                     if expr is None:
#                         expr = e
#                     else:
#                         expr = self.btor.Add(expr, e)
#                          
#             min_v = self.minimize(expr, 0, n_terms)

            # Finalize the value of the field
            for f in rs.fields():
                f.post_randomize()
                f.dispose() # Get rid of the solver var, since we're done with it
            
        for uf in ri.unconstrained():
            uf.set_val(self.randbits(uf.width()))
            
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
            constraint_l : List[ConstraintModel] = []):
        # First, invoke pre_randomize on all elements
        for fm in field_model_l:
            fm.pre_randomize()

        r = Randomizer()
        ri = RandInfoBuilder.build(field_model_l, constraint_l)
        r.randomize(ri)
        
        for fm in field_model_l:
            fm.post_randomize()
        
        
        # Process constraints to identify variable/constraint sets
        
