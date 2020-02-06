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
from vsc.model.coverpoint_bin_enum_model import CoverpointBinEnumModel
import enum
from vsc.model import expr_mode

'''
Created on Aug 3, 2019

@author: ballance
'''

class CoverpointModel():
    
    def __init__(self, parent, facade_obj, name):
        from vsc.types import type_base
        self.parent = parent
        self.fo = facade_obj
        self.name = name
        
        self.bin_model_l = []
        
        with expr_mode():
            print("self.fo.bins=" + str(self.fo.bins))        
            if self.fo.bins is None or len(self.fo.bins) == 0:
                if self.bins is None or len(self.bins) == 0:
                    if self.cp_t == type_base:
                        print("TODO: auto-bins from explicit type")
                elif type(self.cp_t) == enum.EnumMeta:
                    for e in list(self.cp_t):
                        self.bin_model_l.append(CoverpointBinEnumModel(e.name, self, e))
                else:
                    raise Exception("attempting to create auto-bins from unknown type " + str(self.cp_t))       
            else:
                for bin_name,bin_spec in self.fo.bins.items():
                    if not hasattr(bin_spec, "_build_model"):
                        raise Exception("Bin specification doesn't have a _build_model method")
                    print("bin: " + bin_name + " spec=" + str(bin_spec))
                    bin_m = bin_spec._build_model(self, bin_name)
                    self.bin_model_l.append(bin_m)
                
        self.n_bins = 0
        for b in self.bin_model_l:
            self.n_bins += b.get_n_bins()
            
    def get_coverage(self):
        raise Exception("get_coverage unimplemented")
        pass
    
    def get_inst_coverage(self):
        raise Exception("get_inst_coverage unimplemented")
        pass
        
    def sample(self):
        for b in self.bin_model_l:
            b.sample()
            
    def get_val(self):
        return self.fo.get_val()

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
        for bin in self.bin_model_l:
            if bin.hit_idx() != -1:
                bin_l.append(bin_idx + bin.hit_idx())
            bin_idx += bin.n_bins()
        
        