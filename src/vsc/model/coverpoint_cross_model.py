
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



'''
Created on Aug 3, 2019

@author: ballance
'''

class CoverpointCrossModel():
    
    def __init__(self, parent, facade_obj, name):
        self.parent = parent
        self.fo = facade_obj
        self.name = name
        self.coverpoint_model_l = []
        
        for cp in self.fo.target_l:
            m = cp.get_model()
            print("cp m=" + str(m))
            self.coverpoint_model_l.append(m)
            
        self.hit_map = {}
        self.unhit_map = {}
    
        # Build up the hit map    
        self._build_hit_map(0, [])
        pass
    
    def accept(self, v):
        v.visit_coverpoint_cross(self)
    
    def _build_hit_map(self, i, key_m):
        for bin_i in range(self.coverpoint_model_l[i].get_n_bins()):
            key_m.append(bin_i)
            
            if i+1 >= len(self.coverpoint_model_l):
                key = tuple(key_m)
                # Reached the bottom of the list
#                print("Tuple: " + str(key))
                self.hit_map[key] = 0
                self.unhit_map[key] = 0
            else:
                self._build_hit_map(i+1, key_m)
                
            key_m.pop()
    
    def sample(self):
        have_cp_hit = False
        key_m = []
        for cp in self.coverpoint_model_l:
            have_bin_hit = False
            idx = 0
            for b in cp.bin_model_l:
                if b.hit_idx() != -1:
                    key_m.append(b.hit_idx() + idx)
                    have_bin_hit = True
                    break
                else:
                    idx += b.get_n_bins()
                    
            if have_bin_hit:
                have_cp_hit = True
            else:
                have_cp_hit = False
                break
    
        if have_cp_hit:
            key = tuple(key_m)
            self.hit_map[key] += 1
            if not key in self.hit_map.keys():
                self.unhit_map.pop(key)
                
    def dump(self, ind=""):
        print(ind + "Cross: " + self.name)
        for key in self.hit_map.keys():
            print(ind + "    " + str(key) + "=" + str(self.hit_map[key]))
    