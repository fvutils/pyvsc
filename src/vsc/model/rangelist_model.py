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
from typing import List




# Created on Aug 4, 2019
#
# @author: ballance


class RangelistModel(object):
    
    def __init__(self, rl : List[List[int]]=None):
        self.range_l = []

        if rl is not None:
            for r in rl:
                if isinstance(r, (list,tuple)):
                    if len(r) == 2:
                        self.range_l.append([r[0], r[1]])
                    else:
                        raise Exception("Each range element must have 2 elements")
                else:
                    self.range_l.append([int(r), int(r)])
   
                    
    def add_value(self, v):
        self.range_l.append([v, v])

    def add_range(self, low, high):
        self.range_l.append([low, high])
        
    def __contains__(self, val):
        for r in self.range_l:
            if val >= r[0] and val <= r[1]:
                return True
            
        return False
    
    def equals(self, oth)->bool:
        eq = isinstance(oth, RangelistModel)

        if len(self.range_l) == len(oth.range_l):
            for i in range(len(self.range_l)):
                eq &= self.range_l[i][0] == oth.range_l[i][0]
                eq &= self.range_l[i][1] == oth.range_l[i][1]
        else:
            eq = False
            
        return eq
    
    def toString(self):
        ret = "["
        for i,r in enumerate(self.range_l):
            if i > 0:
                ret += ","
            ret += str(r[0]) + ".." + str(r[1])
        ret += "]"
        
        return ret
            

    def clone(self):
        ret = RangelistModel(None)
        
        for r in self.range_l:
            ret.range_l.append([r[0], r[1]])
            
        return ret
    
    def accept(self, v):
        v.visit_rangelist(self);