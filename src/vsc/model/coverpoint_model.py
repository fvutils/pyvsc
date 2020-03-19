
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

from vsc.model.expr_model import ExprModel
from vsc.model.expr_cond_model import ExprCondModel
from vsc.model.expr_literal_model import ExprLiteralModel

'''
Created on Aug 3, 2019

@author: ballance
'''

class CoverpointModel(object):
    
    def __init__(self, target : ExprModel, name : str):
        self.parent = None
        self.target = target

        # Cached value Target-ref field. This is used to retrieve values for
        # type covergroups
        self.target_val_cache = 0

        self.name = name
        self.n_bins = 0
        self.bin_model_l = []
        
        self.srcinfo_decl = None
        self.bin_expr = None
        # Tracks 
        self.coverage = 0.0
        self.coverage_calc_valid = False
            
    def add_bin_model(self, bin_m):
        bin_m.parent = self
        self.bin_model_l.append(bin_m)
        return bin_m
        
    def finalize(self):
        for b in self.bin_model_l:
            b.finalize()
            
        for b in self.bin_model_l:
            self.n_bins += b.get_n_bins()
            
    def get_bin_expr(self, target=None):
        if target is None:
            target = self.target
            
        if self.bin_expr is None and target is not None:
            # Build a bin expression if the target is specified
            expr_l = []
            for b in self.bin_model_l:
                b.get_bin_expr(expr_l, target)

            if len(expr_l) > 1:
                expr_l = ExprCondModel(
                    expr_l[-1],
                    ExprLiteralModel(len(expr_l)-1),
                    -1)
                
                for i in range(len(expr_l)-1):
                    expr = ExprCondModel(
                        expr_l[i],
                        ExprLiteralModel(i),
                        expr_l)
                    expr_l = expr
            else:
                expr = ExprCondModel(
                    expr_l[0],
                    ExprLiteralModel(0),
                    ExprLiteralModel(-1))

                self.bin_expr = expr

        return self.bin_expr
            
    def get_coverage(self):
        if not self.coverage_calc_valid:
            coverage = 0.0
        
            for bin in self.bin_model_l:
                coverage += bin.get_coverage()

            if len(self.bin_model_l) != 0:
                coverage /= len(self.bin_model_l)
            else:
                coverage = 100.0
            self.coverage = coverage
            self.coverage_calc_valid = True
        
        return self.coverage
    
    def get_inst_coverage(self):
        raise Exception("get_inst_coverage unimplemented")
        
    def sample(self):
        for b in self.bin_model_l:
            b.sample()
            
    def coverage_ev(self, ev):
        """Called by a bin to signal that an uncovered bin has been covered"""
        self.coverage_calc_valid = False
            
    def get_val(self):
        if self.target is not None:
            self.target_val_cache = self.target.val()
        return self.target_val_cache
            
    def accept(self, v):
        v.visit_coverpoint(self)
            
    def dump(self, ind=""):
        print(ind + "Coverpoint: " + self.name)
        for b in self.bin_model_l:
            b.dump(ind + "    ")
            
    def get_n_bins(self):
        return self.n_bins
        
    def get_bin_hits(self, bin_idx):
        b = None
        for i in range(len(self.bin_model_l)):
            b = self.bin_model_l[i]
            if b.get_n_bins() > bin_idx:
                break
            bin_idx -= b.get_n_bins()
            
        return b.get_hits(bin_idx)
    
    def get_hit_bins(self, bin_l):
        bin_idx = 0
        for b in self.bin_model_l:
            if b.hit_idx() != -1:
                bin_l.append(bin_idx + b.hit_idx())
            bin_idx += b.n_bins()

    def equals(self, oth:'CoverpointModel')->bool:
        eq = True
        
        eq &= self.name == oth.name
        
        if len(self.bin_model_l) == len(oth.bin_model_l):
            for s,o in zip(self.bin_model_l, oth.bin_model_l):
                eq &= s.equals(o)
        else:
            eq= False
            
        return eq
    
    def clone(self)->'CoverpointModel':
        ret = CoverpointModel(self.target, self.name)
        ret.srcinfo_decl = None if self.srcinfo_decl is None else self.srcinfo_decl.clone()
        
        for bn in self.bin_model_l:
            ret.add_bin_model(bn.clone())

        # TODO: must be more complete        
        
        return ret
        
