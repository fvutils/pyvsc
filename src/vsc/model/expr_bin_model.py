from vsc.model.bin_expr_type import BinExprType

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
Created on Jul 26, 2019

@author: ballance
'''
from vsc.model.expr_model import ExprModel

class ExprBinModel(ExprModel):
    
    def __init__(self, lhs, op, rhs):
        self.lhs = lhs
        self.op = op
        self.rhs = rhs
        self.node = None
        self.width = 0
        self.signed = 0
        
        
    def build(self, builder):
        self.lhs.build(builder)
        self.rhs.build(builder)
        
        lhs_n = self.lhs.get_node()
        rhs_n = self.rhs.get_node()
        
        lhs_n = self.extend(lhs_n, rhs_n, self.lhs.is_signed(), builder.btor)
        rhs_n = self.extend(rhs_n, lhs_n, self.rhs.is_signed(), builder.btor)
        
        if self.op == BinExprType.Eq:
            self.node = builder.btor.Eq(lhs_n, rhs_n)
            pass
        elif self.op == BinExprType.Ne:
            pass
        else:
            raise Exception("Unsupported binary expression type \"" + str(self.op) + "\"")

    def extend(self, e1, e2, signed, btor):
        ret = e1
        
        if e2.width > e1.width:
            if signed:
                ret = btor.Sext(e1, e2.width-e1.width)
            else:
                ret = btor.Uext(e1, e2.width-e1.width)

        return ret        

    def get_node(self):
        return self.node
    
    def is_signed(self):
        return self.signed
    
    def width(self):
        return self.width
        