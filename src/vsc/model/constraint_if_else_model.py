
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
        self.cond = cond
        self.true_c = None
        self.false_c = None
        self.node = None
        
    def build(self, builder):
        self.cond.build(builder)
        self.true_c.build(builder)
        
        e_n = self.cond.get_node()
        
        true_n_l = []
        self.true_c.get_nodes(true_n_l)
        true_n = ConstraintModel.and_nodelist(true_n_l, builder.btor)
        
        if self.false_c == None:
            self.node = builder.btor.Implies(e_n, true_n)
        else:
            self.false_c.build(builder)
            false_n_l = []
            self.false_c.get_nodes(false_n_l)
            print("false_n_l: " + str(len(false_n_l)))
            false_n = ConstraintModel.and_nodelist(false_n_l, builder.btor)
            self.node = builder.btor.Cond(e_n, true_n, false_n)
   
    
    def get_nodes(self, node_l):
        node_l.append(self.node)
        
    def __str__(self):
        ret = "if (" + str(self.cond) + ") { " + str(self.true_c) + " }"
        if self.false_c != None:
            ret += " else { " + str(self.false_c) + " }"
        return ret
    

    def accept(self, visitor):
        visitor.visit_constraint_if_else(self)