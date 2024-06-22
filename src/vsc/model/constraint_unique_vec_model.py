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
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.field_array_model import FieldArrayModel

class ConstraintUniqueVecModel(ConstraintModel):
    
    def __init__(self, unique_l):
        super().__init__()
        self.unique_l = unique_l
        self.expr = None 
        
    def build(self, btor, soft=False):
        ret = None

        # Elements in the unique list might be arrays        
        unique_l = []

        sz = -1
        for i in self.unique_l:
            if sz == -1:
                sz = len(i.fm.field_l)
            elif sz != len(i.fm.field_l):
                raise Exception("All arguments to unique_vec must be of the same size")

        # Form ORs of inequalities across the vector pairs
        and_e = None
        for i in range(len(self.unique_l)):
            for j in range(i+1, len(self.unique_l)):
                v_ne = self._mkVecNotEq(btor, self.unique_l[i], self.unique_l[j])

                if and_e is None:
                    and_e = v_ne
                else:
                    and_e = btor.And(and_e, v_ne)

        return and_e
    
    def _mkVecNotEq(self, btor, v1, v2):
        ret = None
        for i in range(len(v1.fm.field_l)):
            ne = ExprBinModel(
                ExprFieldRefModel(v1.fm.field_l[i]), 
                BinExprType.Ne, 
                ExprFieldRefModel(v2.fm.field_l[i]))
            if ret is None:
                ret = ne.build(btor)
            else:
                ret = btor.Or(ne.build(btor), ret)
        return ret
    
    def accept(self, visitor):
        visitor.visit_constraint_unique_vec(self)
        
    def clone(self, deep=False)->'ConstraintModel':
        ret = ConstraintUniqueVecModel(self.unique_l)
        
        return ret
        