
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
from vsc.types import type_base, field_info, type_enum
from enum import Enum


def attr(t):
    # TODO: why do this?
    return t

def rand_attr(t):
    if isinstance(t, type_base):
        t._int_field_info.is_rand = True
    elif isinstance(t, Enum):
        t = type_enum(t)
    elif hasattr(t, "_int_rand_info"):
        # composite type
        t._int_field_info = field_info()
        t._int_field_info.is_rand = True
        print("t=" + str(t) + " field_info=" + str(t._int_field_info))
    else:
        raise Exception("Attempting to decorate \"" + str(t) + "\" of type \"" + str(type(t)) + "\" as rand")
    
    return t
