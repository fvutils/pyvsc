
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
Created on Jul 28, 2019

@author: ballance
'''
from vsc.model.constraint_model import ConstraintModel
from vsc.model.constraint_scope_model import ConstraintScopeModel


class ConstraintImpliesModel(ConstraintScopeModel):
    
    def __init__(self, cond):
        super().__init__()
        self.cond = cond
        self.node = None
        
    def build(self, builder):
        self.cond.build(builder)
        super().build(builder)
        
        e_n = self.cond.get_node()
        c_l = []
        super().get_nodes(c_l)
        c_n = ConstraintModel.and_nodelist(c_l, builder.btor)
        
        self.node = builder.btor.Implies(e_n, c_n)
    
    def get_nodes(self, node_l):
        node_l.append(self.node)