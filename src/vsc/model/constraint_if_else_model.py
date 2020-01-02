
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

class ConstraintIfElseModel(ConstraintModel):
    
    def __init__(self, cond):
        super().__init__()
        self.cond = cond
        self.true_c = None
        self.false_c = None
        
    def build(self, btor):
        cond = self.cond.build(btor)
        true_c = self.true_c.build(btor)
        
        if self.false_c == None:
            ret = btor.Implies(cond, true_c)
        else:
            false_c = self.false_c.build(btor)
            ret = btor.Cond(cond, true_c, false_c)

        return ret
    
    def get_nodes(self, node_l):
        node_l.append(self.node)
        
    def __str__(self):
        ret = "if (" + str(self.cond) + ") { " + str(self.true_c) + " }"
        if self.false_c != None:
            ret += " else { " + str(self.false_c) + " }"
        return ret
    

    def accept(self, visitor):
        visitor.visit_constraint_if_else(self)