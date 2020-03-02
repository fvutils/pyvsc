
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

from vsc.model.rand_obj_model import RandObjModel
from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.types import type_base, field_info
from vsc.model import _expr_mode, get_expr_mode, expr_mode, get_expr_mode_depth,\
    enter_expr_mode, leave_expr_mode
import sys
from vsc.model.randomizer import Randomizer
from vsc.model.scalar_field_model import ScalarFieldModel
from vsc.constraints import constraint_t


'''
Created on Jul 23, 2019

@author: ballance
'''
from vsc.impl.ctor import register_rand_obj_type, push_constraint_scope,\
    pop_constraint_scope

def randobj(T):
    
    if not hasattr(T, "_ro_init"):
        def __getattribute__(self, a):
            ret = object.__getattribute__(self, a)
        
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
                fo = object.__getattribute__(self, field)
            except:
                object.__setattr__(self, field, val)
            else:
                if isinstance(fo, type_base):
                    if get_expr_mode() == 0:
                        # We're not in an expression context, so the 
                        # user really wants us to set the actual value
                        # of the field
                        fo.set_val(val)
                    else:
                        raise Exception("Attempting to use '=' in a constraint")
                else:
                    object.__setattr__(self, field, val)                
                    
        def randomize(self):
            model = self.get_model()
            Randomizer.do_randomize([model])
            
        def build_field_model(self, name):
            self.model = RandObjModel(name, self)
            
            # Iterate through the fields and constraints
            # First, assign IDs to each of the randomized fields
            with expr_mode():
                for f in dir(self):
                    if not f.startswith("__") and not f.startswith("_int"):
                        fo = getattr(self, f)
                        
                        if hasattr(fo, "build_field_model"):
                            self.model.add_field(fo.build_field_model(f))
                
#                         if isinstance(fo, type_base):
#                             fo._int_field_info.name = f
#                             fo._int_field_info.id = len(model.field_l)
#                             if model.parent is not None:
#                                 # TODO: need a little help here
#                                 fo._int_field_info.parent = self.parent.user_obj._int_field_info
#                             self.add_field(ScalarFieldModel(modelfo, self, 
#                                 (is_rand and fo._int_field_info.is_rand)))
#                         elif hasattr(fo, "_int_field_info"):
#                             # This is a composite field
#                             # TODO: assign ID
#                             fo._int_field_info.name = f
#                             fo._int_field_info.id = len(model.field_l)
#                             if model.parent != None:
#                                 fo._int_field_info.parent = model.parent.t._int_field_info
#                             model.add_field(CompositeFieldModel(fo, self, 
#                                 (is_rand and fo._int_field_info.is_rand)))
                    
                # Now, elaborate the constraints
                for f in dir(self):
                    if not f.startswith("__") and not f.startswith("_int"):
                        fo = getattr(self, f)
                        if isinstance(fo, constraint_t):
                            push_constraint_scope(ConstraintBlockModel(f))
                            try:
                                fo.c(self)
                            except Exception as e:
                                print("Exception while processing constraint: " + str(e))
                                raise e
                            self.model.add_constraint(pop_constraint_scope())
                                    
                return self.model
        
        def get_model(self):
            with expr_mode():
                if not hasattr(self, "model") or self.model is None:
                    self.model = self.build_field_model(None)
                
                return self.model
            
        
        def __enter__(self):
            enter_expr_mode()
            self.get_model() # Ensure model is constructed
            push_constraint_scope(ConstraintBlockModel("inline"))
            return self
        
        def __exit__(self, t, v, tb):
            c = pop_constraint_scope()
            leave_expr_mode()
            Randomizer.do_randomize([self.model], [c])
        
        def randomize_with(self):
            # Ensure the 'model' data structures have been built
            self.get_model()
    
            return self
        
        def pre_randomize(self):
            pass
        
        def post_randomize(self):
            pass                    

        setattr(T, "__getattribute__", __getattribute__)
        setattr(T, "__setattr__", __setattr__)
        setattr(T, "randomize", randomize)
        setattr(T, "randomize_with", randomize_with)
        setattr(T, "build_field_model", build_field_model)
        setattr(T, "get_model", get_model)
        setattr(T, "__enter__", __enter__)
        setattr(T, "__exit__", __exit__)
        setattr(T, "pre_randomize", pre_randomize)
        setattr(T, "post_randomize", post_randomize)
        setattr(T, "_int_field_info", field_info())
        setattr(T, "_ro_init", True)
        
    return T
    

# class RandObj(expr_mode):
#     """Base class for coverage and randomized classes"""
#     
#     _ro_init = True
#    
#     def __init__(self):
#         super().__init__()
#         self._int_field_info = field_info()
#         self.model = None
#         pass
#     
# #     def copy(self, rhs):
# #         if not isinstance(rhs, type(self)):
# #             raise Exception("Error")
# #         
# #         for d in dir(self):
# #             do = getattr(self, d)
# #             if not callable(do):
# #                 # Candidate for copying
# #                 if type(do) == int:
# #                     setattr(self, d, getattr(rhs, d))
# #                 elif hasattr(do, "copy"):
# #                     do.copy(getattr(rhs, d))
# #     
# #     def clone(self):
# #         ret = type(self)()
# #         ret.copy(self)
# #         return ret    
#     
#     def __getattribute__(self, a):
#         ret = super().__getattribute__(a)
#         
#         if isinstance(ret, type_base) and get_expr_mode() == 0:
#             # We're not in an expression, so the user
#             # wants the value of this field
#             ret = ret.get_val()
#             
#         return ret
#     
#     def __setattr__(self, field, val):
#         try:
#             # Retrieve the field object so we can check if it's 
#             # a type_base object. This will throw an exception
#             # if the field doesn't exist
#             fo = super().__getattribute__(field)
#         except:
#             super().__setattr__(field, val)
#         else:
# #            super().__setattr__(field, val)
#             if isinstance(fo, type_base):
#                 if get_expr_mode() == 0:
#                     # We're not in an expression context, so the 
#                     # user really wants us to set the actual value
#                     # of the field
#                     fo.set_val(val)
#                 else:
#                     raise Exception("Attempting to use '=' in a constraint")
#             else:
#                 super().__setattr__(field, val)
# 
#     def randomize(self):
#         model = self.get_model()
#         Randomizer.do_randomize([model])
#         
#     def _build_model(self):
#         return self.build_field_model(None)
#     
#     def get_model(self):
#         with expr_mode():
#             if self.model is None:
#                 self.model = self._build_model()
#             
#             return self.model
#         
#     
#     def __enter__(self):
#         super().__enter__()
#         self.get_model() # Ensure model is constructed
#         push_constraint_scope(ConstraintBlockModel("inline"))
#         return self
#     
#     def __exit__(self, t, v, tb):
#         c = pop_constraint_scope()
#         super().__exit__(t, v, tb)
#         Randomizer.do_randomize([self.model], [c])
#     
#     def randomize_with(self):
#         if self.model is None:
#             # Need to initialize
#             self.model = self._build_model()
# 
#         return self
#     
#     def pre_randomize(self):
#         pass
#     
#     def post_randomize(self):
#         pass
#     

    