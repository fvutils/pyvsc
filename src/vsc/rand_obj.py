from vsc.model.rand_obj_model import RandObjModel
from vsc.model.constraint_scope_model import ConstraintScopeModel

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
from vsc.impl.ctor import register_rand_obj_type, push_constraint_scope,\
    pop_constraint_scope

# TODO: 
def rand_obj(T):
    if not hasattr(T, "_int_rand_info"):
        T._int_rand_info = True
    register_rand_obj_type(T)
    
    return T

class Base():
    """Base class for coverage and randomized classes"""
    
    def __init__(self):
        self.is_rand = False
        self.model = None
        pass

    def copy(self, rhs):
        if not isinstance(rhs, type(self)):
            raise Exception("Error")
        
        for d in dir(self):
            do = getattr(self, d)
            if not callable(do):
                # Candidate for copying
                if type(do) == int:
                    setattr(self, d, getattr(rhs, d))
                elif hasattr(do, "copy"):
                    do.copy(getattr(rhs, d))
    
    def clone(self):
        ret = type(self)()
        ret.copy(self)
        return ret    

    def randomize(self):
        if self.model is None:
            # Need to initialize
            self.model = self._build_model()
            
        return self.model.do_randomize()
    
    def _build_model(self):
        model = RandObjModel(self)
        return model
    
    def __enter__(self):
        push_constraint_scope(ConstraintScopeModel())
        return self
    
    def __exit__(self, t, v, tb):
        c = pop_constraint_scope()
        self.model.do_randomize([c])
    
    def randomize_with(self):
        if self.model is None:
            # Need to initialize
            self.model = self._build_model()

        return self
    
    def pre_randomize(self):
        pass
    
    def post_randomize(self):
        pass
    

    