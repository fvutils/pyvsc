
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
Created on Aug 3, 2019

@author: ballance
'''

class CovergroupModel():
    
    def __init__(self):
        self.coverpoint_l = []
        self.cross_l = []
        self.name = "<default>"
    
    def sample(self):
        
        # First, sample the coverpoints
        for cp in self.coverpoint_l:
            cp.sample()
            
        for cr in self.cross_l:
            cr.sample()
            
    def accept(self, v):
        v.visit_covergroup
            
    def dump(self, ind=""):
        print(ind + "Covergroup " + self.name)
        for cp in self.coverpoint_l:
            cp.dump(ind + "    ")
        for cr in self.cross_l:
            cr.dump(ind + "    ")
            