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

from builtins import zip
import random
from typing import List, Dict

from pyboolector import Boolector, BoolectorNode
import pyboolector

from vsc.constraints import constraint
from vsc.model.constraint_model import ConstraintModel
from vsc.model.constraint_soft_model import ConstraintSoftModel
from vsc.model.field_model import FieldModel
from vsc.model.model_visitor import ModelVisitor
from vsc.model.rand_if import RandIF
from vsc.model.rand_info import RandInfo
from vsc.model.rand_info_builder import RandInfoBuilder


class Randomizer(RandIF):
    """Implements the core randomization algorithm"""
    
    _state_p = [0,1]
    _rng = random.Random()
    
    
    def randomize(self, ri : RandInfo):
        """Randomize the variables and constraints in a RandInfo collection"""
        
        for rs in ri.randsets():
#             print("RandSet:")
#             for f in rs.fields():
#                 print("  Field: " + f.name)
#             for c in rs.constraints():
#                 print("  Constraint: " + str(c))
#             print("Randset: n_fields=" + str(len(rs.fields())))
            btor = Boolector()
            self.btor = btor
            btor.Set_opt(pyboolector.BTOR_OPT_INCREMENTAL, True)
            btor.Set_opt(pyboolector.BTOR_OPT_MODEL_GEN, True)
            
            for f in rs.fields():
                f.build(btor)

            node_l : [BoolectorNode] = []
            soft_node_l : [BoolectorNode] = []
                
            for c in rs.constraints():
                try:
                    n = c.build(btor)
                    if isinstance(c, ConstraintSoftModel):
                        soft_node_l.append(n)
                    else:
                        node_l.append(n)
#                    btor.Assert(c.build(btor))
                    btor.Assume(n)
                except Exception as e:
                    print("Error: The following constraint failed:\n" + str(c))
                    raise e
                        
            
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
                        for f in rs.fields():
                            f.dispose()

                        raise Exception("solve failure")
                    else:
                        # Still need to convert assumptions to assertions
                        for n in filter(lambda n:n is not None, node_l+soft_node_l):
                            btor.Assert(n)
                else:
                    for n in node_l:
                        if btor.Failed(n):
                            print("")
                            
                    # Ensure we clean up
                    for f in rs.fields():
                        f.dispose()
                    raise Exception("solve failure")
            else:
                # Still need to convert assumptions to assertions
                btor.Assert(*(node_l+soft_node_l))
            
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
#             for f in rs.fields():
#                 val = self.randbits(f.width)
#                 bit = self.randint(0, f.width-1)
#                 n = btor.Eq(
#                     btor.Slice(f.var, bit, bit),
#                     btor.Const((val >> bit) & 1, 1))
#                 rand_node_l.append(n)
            btor.Assume(*rand_node_l)
            
            if btor.Sat() != btor.SAT:
                
                # Clear out any failing assumptions
                
                # Try one more time before giving up
                n_failed = 0
                for i,f in enumerate(rand_node_l):
                    if btor.Failed(f):
                        rand_node_l[i] = None
                        n_failed += 1
                        
#                print("n_failed=" + str(n_failed) + " total=" + str(len(rand_node_l)))
                        
                # Add back the hard-constraint nodes and soft-constraints that
                # didn't fail                        
#                 for i,n in enumerate(rand_node_l):
#                     if n is not None:
#                         btor.Assume(n)
                btor.Assume(*filter(lambda n:n is not None, rand_node_l))
                        
                if btor.Sat() != btor.SAT:
                    print("Randomization failed")
                    for i,n in enumerate(rand_node_l):
                        if n is not None:
                            if btor.Failed(n):
                                print("Assumption " + str(i) + " failed")
                    raise Exception("solve failure")
                
            # Finalize the value of the field
            for f in rs.fields():
                f.post_randomize()
                f.dispose() # Get rid of the solver var, since we're done with it

        for uf in ri.unconstrained():
            uf.set_val(self.randbits(uf.width))
            
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
            
        # First, invoke pre_randomize on all elements
        for fm in field_model_l:
            fm.pre_randomize()

        r = Randomizer()
        ri = RandInfoBuilder.build(field_model_l, constraint_l, Randomizer._rng)
        r.randomize(ri)
        
        for fm in field_model_l:
            fm.post_randomize()
        
        
        # Process constraints to identify variable/constraint sets
        
