
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
from vsc.constraints import constraint_t
from vsc.types import type_base

import pyboolector
from pyboolector import Boolector
from vsc.model.composite_field_model import CompositeFieldModel


class RandObjModel(CompositeFieldModel):
    
    def __init__(self, t):
        self.is_elab = False;
        self.seed = 1

        # Each random object gets its own Boolector instance
        self.btor = Boolector()
        self.btor.Set_opt(pyboolector.BTOR_OPT_INCREMENTAL, True)
        self.btor.Set_opt(pyboolector.BTOR_OPT_MODEL_GEN, True)
        
        print("RandObjModel: " + str(t))
        super().__init__(t, None, True, self.btor)

 
        pass
    
    def elab(self):
        if self.is_elab:
            return
        
        
        self.is_elab = True
        
    def next(self):
        self.seed ^= (self.seed >> 12)
        self.seed ^= (self.seed << 25)
        self.seed ^= (self.seed >> 27)

        self.seed &= 0xFFFFFFFF
        
        return ((self.seed * 0x4F6CDD1D) >> 16)        
        
        
    def do_randomize(self):
        self.pre_randomize()
        
        field_l = []
        self.get_fields(field_l)
        
        print("Fields: " + str(len(field_l)))
        
        if self.btor.Sat() != self.btor.SAT:
            print("Error: failed")
            return False

        bits = -1
        if len(field_l) > 4:
            n_target_fields = int(len(field_l)/4)
        else:
            n_target_fields = 1
           
        # TODO: Now, add in some randomization
            # First, randomly select fields
        target_field_l = []
        sel_l = field_l.copy()
        for i in range(n_target_fields):
            seed = self.next()
            print("Get rand field: " + str(len(sel_l)) + " " + str(seed%len(sel_l)))
            target_field_l.append(sel_l.pop(seed % len(sel_l)))
            
        for f in target_field_l:
            print("Rand: " + f.f._int_field_info.name)

        bits = 2
        success = False
        while bits != 0:
            # Create a series of xor slices
            
            
            bits -= 0
        
        
        
        self.post_randomize()
#        do_post_randomize()
        
        
        
        