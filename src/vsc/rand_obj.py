from vsc.model.rand_obj_model import RandObjModel
from vsc.model.constraint_scope_model import ConstraintScopeModel
from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.types import type_base
from vsc.model import _expr_mode, get_expr_mode, expr_mode
import traceback
import sys
from statistics import mode
from vsc.model.randomizer import Randomizer

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
#def rand_obj(T):
#    if not hasattr(T, "_int_rand_info"):
#        T._int_rand_info = True
#    register_rand_obj_type(T)
#    
#    return T

class RandObj(expr_mode):
    """Base class for coverage and randomized classes"""
   
    def __init__(self):
        super().__init__()
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
    
    def __getattribute__(self, a):
        ret = super().__getattribute__(a)
        
        if isinstance(ret, type_base) and get_expr_mode() == 0:
            # We're not in an expression, so the user
            # wants the value of this field
            ret = ret.get_val()
            
        return ret
    
    def __setattr__(self, field, val):
        try:
            # Retrieve the field object so we can check if it's 
            # a type_base object. This will throw an exception
            # if the field doesn't exist
            fo = super().__getattribute__(field)
        except:
            super().__setattr__(field, val)
        else:
#            super().__setattr__(field, val)
            if isinstance(fo, type_base):
                if get_expr_mode() == 0:
                    # We're not in an expression context, so the 
                    # user really wants us to set the actual value
                    # of the field
                    fo.set_val(val)
                else:
                    raise Exception("Attempting to use '=' in a constraint")
            else:
                super().__setattr__(field, val)

    def randomize(self):
        model = self.get_model()
        Randomizer.do_randomize([model])
        
    def _build_model(self):
        model = RandObjModel(self)
        return model
    
    def get_model(self):
        with expr_mode():
            if self.model is None:
                self.model = self._build_model()
            
            return self.model
        
    
    def __enter__(self):
        super().__enter__()
        self.get_model() # Ensure model is constructed
        push_constraint_scope(ConstraintBlockModel("inline"))
        return self
    
    def __exit__(self, t, v, tb):
        c = pop_constraint_scope()
        super().__exit__(t, v, tb)
        Randomizer.do_randomize([self.model], [c])
    
    def randomize_with(self):
        if self.model is None:
            # Need to initialize
            self.model = self._build_model()

        return self
    
    def pre_randomize(self):
        pass
    
    def post_randomize(self):
        pass
    

    