
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

from vsc.model.expr_rangelist_model import ExprRangelistModel
from vsc.model.expr_range_model import ExprRangeModel


'''
Created on Jul 28, 2019

@author: ballance
'''
from vsc.model.expr_model import ExprModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.bin_expr_type import BinExprType

class ExprInModel(ExprModel):
    
    def __init__(self, lhs, rhs):
        self.lhs = lhs
        self.rhs = rhs
        
    def build(self, btor):
        t = None
        expr = None
        for r in self.rhs.rl:
            if isinstance(r, ExprRangeModel):
                t = ExprBinModel(
                    ExprBinModel(self.lhs, BinExprType.Ge, r.lhs),
                    BinExprType.And,
                    ExprBinModel(self.lhs, BinExprType.Le, r.rhs))
            else:
                t = ExprBinModel(self.lhs, BinExprType.Eq, r)
                
            if expr is None:
                expr = t 
            else:
                expr = ExprBinModel(expr, BinExprType.Or, t)
                
        return expr.build(btor) if expr is not None else None
    
    def accept(self, visitor):
        visitor.visit_expr_in(self)
        
    def __str__(self):
        return "ExprIn: " + str(self.lhs) + " in " + str(self.rhs)
        
