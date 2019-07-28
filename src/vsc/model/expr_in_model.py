
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
Created on Jul 28, 2019

@author: ballance
'''
from vsc.model.expr_model import ExprModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.bin_expr_type import BinExprType

class ExprInModel(ExprModel):
    
    def __init__(self, lhs, rhs):
        self.expr = None
        
        for r in rhs:
            if isinstance(r, list):
                t = ExprBinModel(
                    ExprBinModel(lhs, BinExprType.Ge, r[0]),
                    BinExprType.And,
                    ExprBinModel(lhs, BinExprType.Le, r[1]))
            else:
                t = ExprBinModel(lhs, BinExprType.Eq, r)
            
            if self.expr == None:
                self.expr = t
            else:
                self.expr = ExprBinModel(self.expr, BinExprType.Or, t)
                
    def build(self, builder):
        self.expr.build(builder)
    
    def get_node(self):
        return self.expr.get_node()
    
    