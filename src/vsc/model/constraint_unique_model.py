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


# Created on Jul 28, 2019
#
# @author: ballance

from vsc.model.constraint_model import ConstraintModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.bin_expr_type import BinExprType

class ConstraintUniqueModel(ConstraintModel):
    
    def __init__(self, unique_l):
        super().__init__()
        self.unique_l = unique_l
        self.expr = None 
        
    def build(self, btor):
        ret = None
            
        for i in range(len(self.unique_l)):
            for j in range(len(self.unique_l)):
                if i != j:
                    
                    t = ExprBinModel(self.unique_l[i], BinExprType.Ne, self.unique_l[j])
                    
                    if ret is None:
                        ret = t.build(btor)
                    else:
                        ret = btor.And(t.build(btor), ret)
                    
        return ret
        
    def get_nodes(self, node_l):
        node_l.append(self.expr.get_node())
        

    def accept(self, visitor):
        visitor.visit_constraint_unique(self)
        
    def clone(self, deep=False)->'ConstraintModel':
        ret = ConstraintUniqueModel(self.unique_l)
        
        return ret
        