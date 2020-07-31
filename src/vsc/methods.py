
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

# Created on Jul 23, 2019
#
# @author: ballance

from vsc.impl import expr_mode
from vsc.impl.expr_mode import enter_raw_mode, leave_raw_mode, enter_expr_mode,\
    leave_expr_mode
from vsc.model.randomizer import Randomizer
from vsc.types import field_info, type_base
from vsc.impl.ctor import push_constraint_scope, pop_constraint_scope
from vsc.model.constraint_block_model import ConstraintBlockModel


def randomize_with(*args):
    """Randomize a list of variables with an inline constraint"""
    field_l = []
    for v in args:
        if not hasattr(v, "get_model"):
            raise Exception("Parameter \"" + str(v) + " to randomize is not a vsc object")
        field_l.append(v.get_model())
    
    class inline_constraint_collector(object):
        
        def __init__(self, field_l):
            self.field_l = field_l
        
        def __enter__(self):
            # Go into 'expression' mode
            enter_expr_mode()
            push_constraint_scope(ConstraintBlockModel("inline"))
            return self
        
        def __exit__(self, t, v, tb):
            c = pop_constraint_scope()
            leave_expr_mode()
            
            Randomizer.do_randomize(self.field_l, [c])
    
    return inline_constraint_collector(field_l)

def randomize(*args):
    """Randomize a list of variables"""
    fields = []
    for v in args:
        if hasattr(v, "get_model"):
            fields.append(v.get_model());
        else:
            raise Exception("Parameter \"" + str(v) + " to randomize is not a vsc object")
        
    Randomizer.do_randomize(fields)

class raw_mode(object):
    """Raw mode provides raw access to primitive VSC Fields"""
    
    def __enter__(self):
        enter_raw_mode()
    
    def __exit__(self, t, v, tb):
        leave_raw_mode()

