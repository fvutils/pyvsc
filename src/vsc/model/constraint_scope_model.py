
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
Created on Jul 27, 2019

@author: ballance
'''
from vsc.model.constraint_model import ConstraintModel

class ConstraintScopeModel(ConstraintModel):
    
    def __init__(self):
        super().__init__()
        self.constraint_l = []
        
    def build(self, builder):
        for c in self.constraint_l:
            c.build(builder)
            
    def get_nodes(self, node_l):
        for c in self.constraint_l:
            c.get_nodes(node_l)

    def accept(self, visitor):
        visitor.visit_constraint_scope(self)