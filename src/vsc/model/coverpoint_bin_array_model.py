
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

from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.bin_expr_type import BinExprType
from vsc.model.expr_literal_model import ExprLiteralModel


'''
Created on Aug 3, 2019

@author: ballance
'''
from vsc.model.coverpoint_bin_model_base import CoverpointBinModelBase

class CoverpointBinArrayModel(CoverpointBinModelBase):
    
    def __init__(self, name, low, high):
        super().__init__(name)
        self.low = low 
        self.high = high 
        self.hit_bin_idx = -1
        
        self.hit_list = []
        for i in range(self.high-self.low+1):
            self.hit_list.append(0)
        self.coverage = 0.0
        self.coverage_calc_valid = False
            
    def finalize(self):
        super().finalize()
        
    def get_bin_expr(self, target, idx=-1):
        """Builds expressions to represent a single bin"""
        return ExprBinModel(
            target,
            BinExprType.Eq,
            ExprLiteralModel(self.low+idx, False, 32)
        )
            
    def get_coverage(self):
        if not self.coverage_calc_valid:
            coverage = 0.0
        
            for h in self.hit_list:
                coverage += 100.0 if h != 0 else 0

            coverage /= len(self.hit_list)
            self.coverage = coverage
            self.coverage_calc_valid = True
        
        return self.coverage
            
    def sample(self):
        # Query value from the actual coverpoint or expression
#        print("sample: binspec=" + str(self.binspec))
        val = self.cp.get_val()
        print("Sample: " + str(val))
        if val >= self.low and val <= self.high:
            self.hit_bin_idx = val - self.low
            if self.hit_list[val-self.low] == 0:
                # We've just hit a new bin. Notify the coverpoint
                self.coverage_calc_valid = False
                self.cp.coverage_ev(self)
            self.hit_list[val-self.low] += 1
        else:
            self.hit_bin_idx = -1
            
        return self.hit_bin_idx
            
    def dump(self, ind=""):
        for i in range(self.high-self.low+1):
            print(ind + self.name + "[" + str(self.low+i) + "]=" + str(self.hit_list[i]))
            
    def get_hits(self, idx):
        return self.hit_list[idx]
        
    def get_n_bins(self):
        return (self.high-self.low+1)
    
    def hit_idx(self):
        return self.hit_bin_idx    
    
    def accept(self, v):
        v.visit_coverpoint_bin_array(self)

    def equals(self, oth):
        eq = isinstance(oth, CoverpointBinArrayModel)
        
        if eq:
            eq &= super().equals(oth)
            eq &= self.low == oth.low 
            eq &= self.high == oth.high 
            
        return eq

    def clone(self)->'CoverpointBinArrayModel':
        ret = CoverpointBinArrayModel(self.name, self.low, self.high)
        ret.srcinfo_decl = None if self.srcinfo_decl is None else self.srcinfo_decl.clone()
        
        return ret