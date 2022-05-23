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

from vsc1.model.constraint_model import ConstraintModel
from vsc1.model.expr_bin_model import ExprBinModel
from vsc1.model.bin_expr_type import BinExprType
from vsc1.model.expr_fieldref_model import ExprFieldRefModel
from vsc1.model.field_array_model import FieldArrayModel

class ConstraintUniqueModel(ConstraintModel):
    
    def __init__(self, unique_l):
        super().__init__()
        self.unique_l = unique_l
        self.expr = None 
        
    def build(self, btor):
        ret = None

        # Elements in the unique list might be arrays        
        unique_l = []
        
        for i in self.unique_l:
            if isinstance(i, ExprFieldRefModel) and isinstance(i.fm, FieldArrayModel):
                # Collect up the array elements
                self._add_list_elems(unique_l, i.fm)
            else:
                unique_l.append(i)
                
        if len(unique_l) > 1:
            for i in range(len(unique_l)):
                for j in range(i+1, len(unique_l)):
                    t = ExprBinModel(unique_l[i], BinExprType.Ne, unique_l[j])
                    from vsc1.visitors import ModelPrettyPrinter
                        
                    if ret is None:
                        ret = t.build(btor)
                    else:
                        ret = btor.And(t.build(btor), ret)
        else:
            # Size 0,1: Always true
            ret = btor.Const(1, 1)
                    
        return ret
    
    def _add_list_elems(self, unique_l, l : FieldArrayModel):
        for f in l.field_l:
            unique_l.append(ExprFieldRefModel(f))
        
    def get_nodes(self, node_l):
        node_l.append(self.expr.get_node())
        

    def accept(self, visitor):
        visitor.visit_constraint_unique(self)
        
    def clone(self, deep=False)->'ConstraintModel':
        ret = ConstraintUniqueModel(self.unique_l)
        
        return ret
        