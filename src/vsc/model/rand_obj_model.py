
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
        
    def do_randomize(self):
        self.pre_randomize()
        
        if self.btor.Sat() != self.btor.SAT:
            print("Error: failed")
            return False
        
        self.post_randomize()
#        do_post_randomize()
        
        
        
        