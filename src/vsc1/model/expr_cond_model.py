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


# Created on Jan 2, 2020
#
# @author: ballance

from vsc1.model.expr_model import ExprModel

class ExprCondModel(ExprModel):
    
    def __init__(self, cond_e, true_e, false_e):
        super().__init__()
        self.cond_e = cond_e
        self.true_e = true_e
        self.false_e = false_e
        
    def build(self, btor, ctx_width=-1):
        cond_n = self.cond_e.build(btor)
        true_n = self.true_e.build(btor)
        false_n = self.false_e.build(btor)
        
        return btor.Cond(cond_n, true_n, false_n)
    
    def is_signed(self):
        return self.true_e.signed or self.false_e.signed
    
    def width(self):
        return 0
        
    def accept(self, visitor):
        visitor.visit_expr_cond(self)
