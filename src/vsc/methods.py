
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
from vsc.types import field_info


def randomize(t):
    print("randomize: t=" + str(t))
    if not hasattr(t, "_int_rand_info"):
        raise Exception("Error: not a random class")

    # Build a model for this object if one doesn't exist already
    if not hasattr(t, "_int_model") or t._int_model is None:
        t._int_field_info = field_info()
        t._int_model = RandObjModel(t)
        
    t._int_model.do_randomize()
    
    pass

def randomize_with(t):
    pass
