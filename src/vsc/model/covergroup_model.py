
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
from vsc.model.coverpoint_cross_model import CoverpointCrossModel

'''
Created on Aug 3, 2019

@author: ballance
'''

class CovergroupModel(object):
    
    def __init__(self):
        self.coverpoint_l = []
        self.cross_l = []
        self.name = "<default>"
        
    def finalize(self):
        pass

    def sample(self):
        
        # First, sample the coverpoints
        for cp in self.coverpoint_l:
            cp.sample()
            
        for cr in self.cross_l:
            cr.sample()
            
    def add_coverpoint(self, cp):
        if isinstance(cp, CoverpointModel):
            self.coverpoint_l.append(cp)
        elif isinstance(cp, CoverpointCrossModel):
            self.cross_l.append(cp)
        else:
            raise Exception("Unsupported model type %s" % (str(type(cp))))
        
    def get_coverage(self):
        return 0.0
    
    def get_inst_coverage(self):
        return 0.0
            
    def accept(self, v):
        v.visit_covergroup(self)
            
    def dump(self, ind=""):
        print(ind + "Covergroup " + self.name)
        for cp in self.coverpoint_l:
            cp.dump(ind + "    ")
        for cr in self.cross_l:
            cr.dump(ind + "    ")
            