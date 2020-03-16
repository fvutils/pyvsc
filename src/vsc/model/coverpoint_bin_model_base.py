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
Created on Aug 4, 2019

@author: ballance
'''

from vsc.model.coverpoint_model import CoverpointModel


class CoverpointBinModelBase(object):
    
    def __init__(self, name):
        self.parent = None
        self.name = name
        self.cp = None
        
        self.srcinfo_decl = None

    def finalize(self):
        cp = self.parent
        while cp is not None and not isinstance(cp, CoverpointModel):
            cp = cp.parent
        self.cp = cp
                
    def n_bins(self):
        return 1
    
    def hit_idx(self):
        return -1
    
    def equals(self, oth):
        eq = isinstance(oth, CoverpointBinModelBase)
        
        if eq:
            eq &= self.name == oth.name
        
        return eq
