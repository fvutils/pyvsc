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

from vsc.impl.ctor import push_expr, pop_expr
from vsc.model.bin_expr_type import BinExprType
from vsc.model.expr_bin_model import ExprBinModel

def unsigned(v, w=-1):
    pass

def signed(v, w=-1):
    pass

class expr():
    def __init__(self, em):
        push_expr(self)
        self.em = em

def to_expr(t):
    if type(t) == int:
        # TODO: literal int
        pass
    elif hasattr(t, "to_expr"):
        return t.to_expr()
    else:
        raise Exception("Element \"" + str(t) + "\" isn't recognized, and doesn't provide to_expr")
    
    
class field_info():
    def __init__(self):
        self.id = -1
        self.name = None
        self.is_rand = False
        
class type_base():
    
    def __init__(self, width, is_signed):
        self.width = width
        self.is_signed = is_signed
        self.val = 0
        self._int_field_info = field_info()
        
    def to_expr(self):
        # TODO: return a field ref
        pass
    
    def bin_expr(self, op, rhs):
        to_expr(rhs)
       

        # TODO: field-reference model
#        push_expr(e)

        lhs_e = pop_expr()
        rhs_e = pop_expr()
        
        e = ExprBinModel(lhs_e.em, op, rhs_e.em)
        
        return expr(e)

    def __eq__(self, rhs):
        return self.bin_expr(BinExprType.Eq, rhs)
    
    def __ne__(self, rhs):
        return self.bin_expr(BinExprType.Ne, rhs)
    
    def __le__(self, rhs):
        return self.bin_expr(BinExprType.Le, rhs)
    
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
        
    def __int__(self):
        return self.val
        
        
class bit_t(type_base):
    
    def __init__(self, w=1):
        super().__init__(w, False)
    
def rand_attr(t):
    pass