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


from vsc.impl.ctor import push_constraint_scope, push_constraint_stmt, pop_expr, \
    pop_constraint_scope, in_constraint_scope, last_constraint_stmt, push_expr
from vsc.model.constraint_if_else_model import ConstraintIfElseModel
from vsc.model.constraint_implies_model import ConstraintImpliesModel
from vsc.model.constraint_scope_model import ConstraintScopeModel
from vsc.model.constraint_soft_model import ConstraintSoftModel
from vsc.model.constraint_unique_model import ConstraintUniqueModel
from vsc.model.expr_dynref_model import ExprDynRefModel
from vsc.types import to_expr, expr
from vsc.model.constraint_foreach_model import ConstraintForeachModel
from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel


class constraint_t(object):
    
    def __init__(self, c):
        self.c = c
        self.enabled = True
        self.model = None
        pass
    
    def constraint_mode(self, en):
        self.enabled = en
        if self.model is not None:
            self.model.set_constraint_enabled(en)
            
    def set_model(self, m):
        self.model = m
        self.model.set_constraint_enabled(self.enabled)
            
    
    def elab(self):
        print("elab")
        
class dynamic_constraint_t(object):
    # TODO:
    
    def __init__(self, c):
        self.c = c
        self.model = None
        
    def set_model(self, m):
        self.model = m
        
    def __call__(self):
        return expr(ExprDynRefModel(self.model))

    class call_closure(object):
        
        def __init__(self, c, *args, **kwargs):
            self.c = c
            self.args = args
            self.kwargs = kwargs
            
        def __enter__(self):
            self.c(*self.args, **self.kwargs)
        
        def __exit__(self, t, v, tb):
            pass
        

def dynamic_constraint(c):
    return dynamic_constraint_t(c)

def constraint(c):
    return constraint_t(c)

class if_then(object):

    def __init__(self, e):
        if not in_constraint_scope():
            raise Exception("Attempting to use if_then constraint outside constraint scope")
        
        to_expr(e)
        self.stmt = ConstraintIfElseModel(pop_expr())
        push_constraint_stmt(self.stmt)
        
    def __enter__(self):
        self.stmt.true_c = ConstraintScopeModel()
        push_constraint_scope(self.stmt.true_c)
        
    def __exit__(self, t, v, tb):
        pop_constraint_scope()
        
        
class else_if(object):

    def __init__(self, e):
        self.stmt = None
        
        if not in_constraint_scope():
            raise Exception("Attempting to use if_then constraint outside constraint scope")
        
        last_stmt = last_constraint_stmt()
        if last_stmt == None or not isinstance(last_stmt, ConstraintIfElseModel):
            raise Exception("Attempting to use else_if where it doesn't follow if_then")
        
        to_expr(e)
        # Need to find where to think this in
        while last_stmt.false_c != None:
            last_stmt = last_stmt.false_c
            
        self.stmt = ConstraintIfElseModel(pop_expr())
        last_stmt.false_c = self.stmt
        
    def __enter__(self):
        if self.stmt is not None:
            self.stmt.true_c = ConstraintScopeModel()
            push_constraint_scope(self.stmt.true_c)
        
    def __exit__(self, t, v, tb):
        pop_constraint_scope()
        
class else_then(object):

    def __init__(self):
        self.stmt = None
        if not in_constraint_scope():
            raise Exception("Attempting to use if_then constraint outside constraint scope")
        
        last_stmt = last_constraint_stmt()
        if last_stmt == None or not isinstance(last_stmt, ConstraintIfElseModel):
            raise Exception("Attempting to use else_then where it doesn't follow if_then/else_if")
        
        # Need to find where to think this in
        while last_stmt.false_c != None:
            last_stmt = last_stmt.false_c
            
        self.stmt = ConstraintScopeModel()
        last_stmt.false_c = self.stmt
        
    def __enter__(self):
        push_constraint_scope(self.stmt)
        
    def __exit__(self, t, v, tb):
        pop_constraint_scope()        

class implies(object):

    def __init__(self, e):
        if not in_constraint_scope():
            raise Exception("Attempting to use if_then constraint outside constraint scope")
        
        to_expr(e)
        self.stmt = ConstraintImpliesModel(pop_expr())
        
    def __enter__(self):
        push_constraint_stmt(self.stmt)
        push_constraint_scope(self.stmt)
        
    def __exit__(self, t, v, tb):
        pop_constraint_scope()
        
def soft(e):
    
    to_expr(e)
    push_constraint_stmt(ConstraintSoftModel(pop_expr()))
    

def unique(*args):
    expr_l = []
    for i in range(-1, -(len(args)+1), -1):
        to_expr(args[i])
        expr_l.insert(0, pop_expr())
        
    push_constraint_stmt(ConstraintUniqueModel(expr_l))

class forall(object):
    
    def __init__(self, target_type):
        self.target_type = target_type
        pass
    
    def __enter__(self):
        pass
    
    def __exit__(self, t, v, tb):
        pass
    
class foreach(object):
    
    def __init__(self, l, it=True, idx=False):
        self.stmt = None
        self.it = it
        self.idx = idx
        self.arr_model = l._int_field_info.model
        if not in_constraint_scope():
            raise Exception("Attempting to use foreach constraint outside constraint scope")

        to_expr(l)
        e = pop_expr()
        self.stmt = ConstraintForeachModel(e)
        
    def __enter__(self):
        push_constraint_stmt(self.stmt)
        push_constraint_scope(self.stmt)
        model = self.arr_model
#        return expr(ExprArraySubscriptModel())
        if self.idx and self.it:
            return (
                expr(ExprFieldRefModel(self.stmt.index)),
                expr(ExprArraySubscriptModel(
                    ExprFieldRefModel(model),
                    ExprFieldRefModel(self.stmt.index)))
                )
        else:
            if self.it:
                return expr(ExprArraySubscriptModel(
                    ExprFieldRefModel(model),
                    ExprFieldRefModel(self.stmt.index)))
            else:
                return expr(ExprFieldRefModel(self.stmt.index))
                
            
        if self.idx:
            return (0,1)
        else:
            return 0

    def __exit__(self, t, v, tb):
        pop_constraint_scope()
        
        