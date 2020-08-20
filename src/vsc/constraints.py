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
    pop_constraint_scope, in_constraint_scope, last_constraint_stmt, push_expr, \
    push_foreach_arr, pop_foreach_arr
from vsc.model.dist_weight_expr_model import DistWeightExprModel
from vsc.model.constraint_foreach_model import ConstraintForeachModel
from vsc.model.constraint_if_else_model import ConstraintIfElseModel
from vsc.model.constraint_implies_model import ConstraintImpliesModel
from vsc.model.constraint_scope_model import ConstraintScopeModel
from vsc.model.constraint_soft_model import ConstraintSoftModel
from vsc.model.constraint_unique_model import ConstraintUniqueModel
from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel
from vsc.model.expr_dynref_model import ExprDynRefModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.types import to_expr, expr, type_base, rng
from vsc.model.constraint_dist_model import ConstraintDistModel

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

class weight(object):
    
    def __init__(self, val, w):
        rng_lhs_e = None
        rng_rhs_e = None
    
        if isinstance(val, (list,tuple)):
            if len(val) != 2:
                raise Exception("Weight range must have two elements")
            to_expr(val[0])
            to_expr(val[1])
            rng_rhs_e = pop_expr()
            rng_lhs_e = pop_expr()
        elif isinstance(val, rng):
            to_expr(val.low)
            to_expr(val.high)
            rng_rhs_e = pop_expr()
            rng_lhs_e = pop_expr()
        else:
            to_expr(val)
            rng_lhs_e = pop_expr()
        to_expr(w)
        w_e = pop_expr()
    
        self.weight_e = DistWeightExprModel(
            rng_lhs_e,
            rng_rhs_e,
            w_e)
    

def dist(lhs, weights):
    """Applies distribution weights to the specified field"""
    
    to_expr(lhs)
    lhs_e = pop_expr()
    
    weight_l = []
    for w in weights:
        if not isinstance(w, weight):
            raise Exception("Weight specifications must of type 'vsc.weight', not " + 
                            str(w))
        weight_l.append(w.weight_e)
        
    push_constraint_stmt(ConstraintDistModel(lhs_e, weight_l))
    

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
        
class else_then_c(object):

    def __init__(self):
        pass
    
    def __call__(self):
        return self
        
    def __enter__(self):
        if not in_constraint_scope():
            raise Exception("Attempting to use if_then constraint outside constraint scope")
        
        last_stmt = last_constraint_stmt()
        if last_stmt == None or not isinstance(last_stmt, ConstraintIfElseModel):
            raise Exception("Attempting to use else_then where it doesn't follow if_then/else_if")
        
        # Need to find where to think this in
        while last_stmt.false_c != None:
            last_stmt = last_stmt.false_c
            
        stmt = ConstraintScopeModel()
        last_stmt.false_c = stmt
        push_constraint_scope(stmt)
        
    def __exit__(self, t, v, tb):
        pop_constraint_scope()

else_then = else_then_c()

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
    
    class idx_term_c(type_base):
        def __init__(self, index):
            super().__init__(32, False)
            self.index = index
        def to_expr(self):
            return expr(ExprFieldRefModel(self.index))
        
    class it_term_c(type_base):
        def __init__(self, it):
            super().__init__(32, False)
            self.it = it
        def to_expr(self):
            return expr(self.it)
    
    def __init__(self, l, it=None, idx=None):
        self.stmt = None
        
        if it is None and idx is None:
            # Default: use it
            it = True
            idx = False
        else:
            # One or more are specified
            if idx is None:
                idx = False
            if it is None:
                it = False
                
        if not idx and not it:
            raise Exception("Neither it nor idx specified")
            
        self.it = it
        self.idx = idx
        self.arr = l
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

        push_foreach_arr(self.arr)

        idx_term = foreach.idx_term_c(self.stmt.index)
        if self.arr_model.is_scalar:
            it_term = foreach.it_term_c(ExprArraySubscriptModel(
                ExprFieldRefModel(model),
                ExprFieldRefModel(self.stmt.index)))
        else:
            self.arr.t._int_field_info.root_e = ExprArraySubscriptModel(
                ExprFieldRefModel(model),
                ExprFieldRefModel(self.stmt.index))
            it_term = self.arr.t
        
        if self.idx and self.it:
            return (idx_term, it_term)
        else:
            if self.it:
                return it_term
            else:
                return idx_term

    def __exit__(self, t, v, tb):
        pop_constraint_scope()
        pop_foreach_arr()
        
        