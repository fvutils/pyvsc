
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


# Created on Jan 25, 2020
#
# @author: ballance

from vsc1.model.expr_model import ExprModel
from typing import List

class ExprRangelistModel(ExprModel):
    
    def __init__(self, rl : List[ExprModel]=None):
        super().__init__()
        if rl is not None:
            self.rl = rl
        else:
            self.rl = []
        
    def add_range(self, r):
        self.rl.append(r)
        
    def accept(self, v):
        v.visit_expr_rangelist(self)
        
    def __str__(self):
        ret = "["
        for i,ri in enumerate(self.rl):
            ret += str(ri)
            if i+1 < len(self.rl):
                ret += ","
        ret += "]"
        return ret