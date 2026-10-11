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

from vsc.model.expr_model import ExprModel

class ExprCondModel(ExprModel):
    
    def __init__(self, cond_e, true_e, false_e):
        super().__init__()
        self.cond_e = cond_e
        self.true_e = true_e
        self.false_e = false_e
        
    def build(self, btor, ctx_width=-1):
        # SV '?:': a wide condition is a truth test, and both arms take the
        # width of the wider arm or the context, whichever is wider.
        from vsc.model.expr_bin_model import ExprBinModel
        cond_n = ExprModel.toBool(btor, self.cond_e.build(btor))
        w = max(ctx_width, int(self.width()))
        signed = self.is_signed()
        true_n = ExprBinModel.extend(self.true_e.build(btor, w), w, signed, btor)
        false_n = ExprBinModel.extend(self.false_e.build(btor, w), w, signed, btor)

        return btor.Cond(cond_n, true_n, false_n)

    def is_signed(self):
        return self.true_e.is_signed() and self.false_e.is_signed()

    def width(self):
        return max(int(self.true_e.width()), int(self.false_e.width()))

    def accept(self, visitor):
        visitor.visit_expr_cond(self)
