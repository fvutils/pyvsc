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
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.expr_in_model import ExprInModel
'''
Created on Jul 23, 2019

@author: ballance
'''

from vsc.impl.ctor import push_expr, pop_expr, in_constraint_scope
from vsc.model.bin_expr_type import BinExprType
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel


def unsigned(v, w=-1):
    if w == -1:
        w = 32
    return expr(ExprLiteralModel(v, False, w))

def signed(v, w=-1):
    if w == -1:
        w = 32
    return expr(ExprLiteralModel(v, True, w))

class expr():
    def __init__(self, em):
        push_expr(em)
        self.em = em
        
class rangelist():
    
    def __init__(self, *args):
        if len(args) == 0:
            raise Exception("Empty rangelist specified")
        
        self.range_l = []
        for i in range(-1,-(len(args)+1), -1):
            a = args[i]
            if isinstance(a, list):
                # This needs to be a two-element array
                if len(a) != 2:
                    raise Exception("Range specified with " + str(len(a)) + " elements is invalid. Two elements required")
                to_expr(a[0])
                to_expr(a[1])
                e1 = pop_expr()
                e0 = pop_expr()
                self.range_l.append([e0, e1])
            else:
                to_expr(a)
                e = pop_expr()
                self.range_l.append(e)

                # This needs to be convertioble to a
            
    def __contains__(self, lhs):
        to_expr(lhs)
        return expr(ExprInModel(pop_expr(), self.range_l))

def to_expr(t):
    if isinstance(t, expr):
        return t
    elif type(t) == int:
        return expr(ExprLiteralModel(t, True, 32))
    elif hasattr(t, "to_expr"):
        return t.to_expr()
    elif callable(t):
        raise Exception("TODO: support lambda references")
    else:
        raise Exception("Element \"" + str(t) + "\" isn't recognized, and doesn't provide to_expr")
    
    
class field_info():
    def __init__(self):
        self.id = -1
        self.name = None
        self.is_rand = False
        self.model = None
        
class type_base():
    
    def __init__(self, width, is_signed, i=0):
        self.width = width
        self.is_signed = is_signed
        self.val = i
        self._int_field_info = field_info()
        
    def to_expr(self):
        return expr(ExprFieldRefModel(self._int_field_info.model))
    
    def __call__(self, v=None):
        '''
        Obtains or sets the current value of the field
        '''
        if v != None:
            self.val = v

        return self.val
    
    def get_val(self):
        print("type_base.get_val: " + str(self.val))
        return self.val
    
    def set_val(self, val):
        self.val = val
    
    def __int__(self):
        return self.val
        
    
    def bin_expr(self, op, rhs):
        to_expr(rhs)
       
        push_expr(ExprFieldRefModel(self._int_field_info.model))

        lhs_e = pop_expr()
        rhs_e = pop_expr()
        
        e = ExprBinModel(lhs_e, op, rhs_e)
        
        return expr(e)

    def __eq__(self, rhs):
        return self.bin_expr(BinExprType.Eq, rhs)
    
    def __ne__(self, rhs):
        return self.bin_expr(BinExprType.Ne, rhs)
    
    def __le__(self, rhs):
        # TODO: overload for behavioral assign
        if in_constraint_scope():
            return self.bin_expr(BinExprType.Le, rhs)
        else:
            self.set_val(rhs)
    
    def __lt__(self, rhs):
        return self.bin_expr(BinExprType.Lt, rhs)
    
    def __ge__(self, rhs):
        return self.bin_expr(BinExprType.Ge, rhs)
    
    def __gt__(self, rhs):
        return self.bin_expr(BinExprType.Gt, rhs)
    
    def __add__(self, rhs):
        return self.bin_expr(BinExprType.Add, rhs)
    
    def __sub__(self, rhs):
        return self.bin_expr(BinExprType.Sub, rhs)
    
    def __getitem__(self, val):
        print("getitem: " + str(val))
        if isinstance(val, slice):
            # slice
            pass
        else:
            # assume single value
            pass
        
    def clone(self):
        return type_base(self.width, self.is_signed)
        
        

class type_enum(type_base):
    
    def __init__(self, t):        
        pass
        
class bit_t(type_base):
    
    def __init__(self, w=1, i=0):
        super().__init__(w, False, i)

class rand_bit_t(bit_t):
    
    def __init__(self, w=1, i=0):
        super().__init__(w, i)
        self._int_field_info.is_rand = True
        
class int_t(type_base):
    
    def __init__(self, w=32, i=0):
        super().__init__(w, True, i)

class rand_int_t(int_t):
    
    def __init__(self, w=32, i=0):
        super().__init__(w, i)
        self._int_field_info.is_rand = True
        
        
