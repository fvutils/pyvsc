from vsc.rand_obj import RandObj
from vsc.model import expr_mode

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

from vsc.model.rand_obj_model import RandObjModel
from vsc.types import field_info, type_base

def randomize_with(*args):
    """Randomize a list of variables with an inline constraint"""
    for a in args:
        if not isinstance(a, (RandObj, type_base)):
            raise Exception("Argument is of type " + str(type(a)) + " not RandObj or type_base")
    
    class inline_constraint_collector(expr_mode):
        
        def __init__(self, *args):
            self.args = args
            pass
        
        def __enter__(self):
            # Go into 'expression' mode
            super().__enter__()
        
        def __exit__(self, t, v, tb):
            super().__exit__(t, v, tb)
    
    return inline_constraint_collector(args)

def randomize(*args):
    """Randomize a list of variables"""
    
    with randomize_with(*args):
        pass
    
