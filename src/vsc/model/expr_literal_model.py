
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
Created on Jul 27, 2019

@author: ballance
'''
from vsc.model.expr_model import ExprModel

class ExprLiteralModel(ExprModel):
    
    def __init__(self, val, is_signed, width):
        self._val = val
        self.signed = is_signed
        self.width = width
        
    def build(self, btor):
        return btor.Const(self.val, self.width)
    
    def get_node(self):
        return self.node
        pass
    
    def is_signed(self):
        return self.signed
    
    def width(self):
        return self.width
   
    def accept(self, visitor):
        visitor.visit_expr_literal(self)
        
    def val(self):
        return self._val
        
    def __str__(self):
        return "Literal: " + str(self.val)
        