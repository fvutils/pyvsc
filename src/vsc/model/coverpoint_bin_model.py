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
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.bin_expr_type import BinExprType
from vsc.model.expr_literal_model import ExprLiteralModel


'''
Created on Aug 3, 2019

@author: ballance
'''
from vsc.types import rangelist
from vsc.model.rangelist_model import RangelistModel
from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.coverpoint_bin_model_base import CoverpointBinModelBase

class CoverpointBinModel(CoverpointBinModelBase):
    """Coverpoint single bin that is triggered on a set of values or value ranges"""
    
    def __init__(self, name, binspec : RangelistModel):
        super().__init__(name)
        self.binspec = binspec
        self.hit_bin_idx = -1
        self.n_hits = 0
        
    def finalize(self):
        super().finalize()
        
    def get_bin_expr(self, expr_l, target):
        """Builds expressions to represent the values in this bin"""
        expr = None
        for r in self.binspec.range_l:
            if r[0] == r[1]:
                e = ExprBinModel(
                    target,
                    BinExprType.Eq,
                    ExprLiteralModel(r[0]))
            else:
                e = ExprBinModel(
                    ExprBinModel(
                        target,
                        BinExprType.Ge,
                        ExprLiteralModel(r[0])),
                    BinExprType.And,
                    ExprBinModel(
                        target,
                        BinExprType.Le,
                        ExprLiteralModel(r[1])))
            if expr is None:
                expr = e
            else:
                expr = ExprBinModel(
                    expr,
                    BinExprType.Or,
                    e)

        expr_l.append(expr)
            
        
    def sample(self):
        # Query value from the actual coverpoint or expression
        val = self.cp.get_val()
        if val in self.binspec:
            self.hit_bin_idx = 0
            self.n_hits += 1
        else:
            self.hit_bin_idx = -1
            
    def dump(self, ind=""):
        print(ind + "Bin " + self.name + " hits: " + str(self.n_hits))
            
    def get_hits(self, idx):
        return self.n_hits
        
    def get_n_bins(self):
        return 1
    
    def hit_idx(self):
        return self.hit_bin_idx
    
    def accept(self, v):
        v.visit_coverpoint_bin(self)

    def equals(self, oth)->bool:
        eq = isinstance(oth, CoverpointBinModel)
        
        if eq:
            eq &= self.binspec.equals(oth.binspec)
            
        return eq
    
    def clone(self)->'CoverpointBinModel':
        ret = CoverpointBinModel(self.name, self.binspec.clone())
        ret.srcinfo_decl = None if self.srcinfo_decl is None else self.srcinfo_decl.clone()
        
        return ret
    
    