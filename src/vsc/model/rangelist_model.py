
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

class RangelistModel(object):
    
    def __init__(self, rl):
        self.range_l = []
        for r in rl:
            if isinstance(r, list):
                if len(r) == 2:
                    self.range_l.append([r[0], r[1]])
                else:
                    raise Exception("Each range element must have 2 elements")
            else:
                self.range_l.append([int(r), int(r)])
                
    
    def __contains__(self, val):
        for r in self.range_l:
            if val >= r[0] and val <= r[1]:
                return True
            
        return False
        