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

# Created on Jul 26, 2019
#
# @author: ballance

from vsc.model.expr_model import ExprModel
from vsc.model.bin_expr_type import BinExprType
from vsc.model.field_composite_model import FieldCompositeModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.field_scalar_model import FieldScalarModel

class ExprBinModel(ExprModel):
    
    def __init__(self, lhs, op, rhs):
        super().__init__()
        self.lhs = lhs
        self.op = op
        self.rhs = rhs
        self.width = 0
        self.signed = 0
        self.is_composite = False
        
        if isinstance(lhs, ExprFieldRefModel) and isinstance(lhs.fm, FieldCompositeModel):
            if isinstance(rhs, ExprFieldRefModel) and isinstance(rhs.fm, FieldCompositeModel):
                self.is_composite = True
                if len(lhs.fm.field_l) != len(rhs.fm.field_l):
                    raise Exception("Incorrect number of fields")
            else:
                raise Exception("BinExpr between composite and non-composite: " + str(lhs) + " ; " + str(rhs))
        
    def build_composite(self, btor, lhs, rhs):
        print("build_composite: " + str(type(lhs)))
        
        if isinstance(lhs, FieldCompositeModel):
            # Keep recursing
            ret = None

            and_l = []            
            for i in range(len(lhs.field_l)):
                lhs_f = lhs.field_l[i]
                rhs_f = rhs.field_l[i]
                and_l.append(self.build_composite(btor, lhs_f, rhs_f))
                
            ret = btor.And(*and_l)
        else:
            if self.op == BinExprType.Eq:
                ret = btor.Eq(
                    lhs.build(btor),
                    rhs.build(btor))
            elif self.op == BinExprType.Ne:
                ret = btor.Ne(
                    lhs.build(btor),
                    rhs.build(btor))
                
        return ret
            

    def build(self, btor):
        ret = None
        if self.is_composite:
            return self.build_composite(btor, self.lhs.fm, self.rhs.fm)
        
        lhs_n = self.lhs.build(btor)
        if lhs_n is None:
            raise Exception("Expression " + str(self.lhs) + " build returned None")
        
        rhs_n = self.rhs.build(btor)
        if rhs_n is None:
            raise Exception("Expression " + str(self.rhs) + " build returned None")
        
        lhs_n = ExprBinModel.extend(lhs_n, rhs_n, self.lhs.is_signed(), btor)
        rhs_n = ExprBinModel.extend(rhs_n, lhs_n, self.rhs.is_signed(), btor)
        
        if self.op == BinExprType.Eq:
            ret = btor.Eq(lhs_n, rhs_n)
        elif self.op == BinExprType.Ne:
            ret = btor.Ne(lhs_n, rhs_n)
        elif self.op == BinExprType.Gt:
            if not self.lhs.is_signed() or not self.rhs.is_signed():
                ret = btor.Ugt(lhs_n, rhs_n)
            else:
                ret = btor.Sgt(lhs_n, rhs_n)
        elif self.op == BinExprType.Ge:
            if not self.lhs.is_signed() or not self.rhs.is_signed():
                ret = btor.Ugte(lhs_n, rhs_n)
            else:
                ret = btor.Sgte(lhs_n, rhs_n)
        elif self.op == BinExprType.Lt:
            if not self.lhs.is_signed() or not self.rhs.is_signed():
                ret = btor.Ult(lhs_n, rhs_n)
            else:
                ret = btor.Slt(lhs_n, rhs_n)
        elif self.op == BinExprType.Le:
            if not self.lhs.is_signed() or not self.rhs.is_signed():
                ret = btor.Ulte(lhs_n, rhs_n)
            else:
                ret = btor.Slte(lhs_n, rhs_n)
        elif self.op == BinExprType.Add:
            ret = btor.Add(lhs_n, rhs_n)
        elif self.op == BinExprType.Sub:
            ret = btor.Sub(lhs_n, rhs_n)
        elif self.op == BinExprType.Div:
            ret = btor.Udiv(lhs_n, rhs_n)
        elif self.op == BinExprType.Mul:
            ret = btor.Mul(lhs_n, rhs_n)
        elif self.op == BinExprType.Mod:
            ret = btor.Urem(lhs_n, rhs_n)
        elif self.op == BinExprType.And:
            ret = btor.And(lhs_n, rhs_n)
        elif self.op == BinExprType.Or:
            ret = btor.Or(lhs_n, rhs_n)
        elif self.op == BinExprType.Sll:
            ret = btor.Sll(lhs_n, rhs_n)
        elif self.op == BinExprType.Srl:
            ret = btor.Srl(lhs_n, rhs_n)
        elif self.op == BinExprType.Xor:
            ret = btor.Xor(lhs_n, rhs_n)
        elif self.op == BinExprType.Not:
            ret = btor.Not(lhs_n, rhs_n)
        else:
            raise Exception("Unsupported binary expression type \"" + str(self.op) + "\"")
        
        return ret

    @staticmethod
    def extend(e1, e2, signed, btor):
        ret = e1
        
        if e2.width > e1.width:
            if signed:
                ret = btor.Sext(e1, e2.width-e1.width)
            else:
                ret = btor.Uext(e1, e2.width-e1.width)

        return ret        

    def is_signed(self):
        return self.signed
    
    def __str__(self):
        return "ExprBin: " + str(self.lhs) + " " + str(self.op) + " " + str(self.rhs)
        
    def accept(self, visitor):
        visitor.visit_expr_bin(self)
        
    def val(self):
        lhs = self.lhs.val()
        rhs = self.rhs.val()
        ret = None
        
        if self.op == BinExprType.Eq:
            ret = (lhs == rhs)
        elif self.op == BinExprType.Ne:
            ret = (lhs != rhs)
        elif self.op == BinExprType.Gt:
            ret = (lhs > rhs)
        elif self.op == BinExprType.Ge:
            ret = (lhs >= rhs)
        elif self.op == BinExprType.Lt:
            ret = (lhs < rhs)
        elif self.op == BinExprType.Le:
            ret = (lhs <= rhs)
        elif self.op == BinExprType.Add:
            ret = (lhs + rhs)
        elif self.op == BinExprType.Sub:
            ret = (lhs - rhs)
        elif self.op == BinExprType.Div:
            ret = (lhs / rhs)
        elif self.op == BinExprType.Mul:
            ret = (lhs * rhs)
        elif self.op == BinExprType.Mod:
            ret = (lhs % rhs)
        elif self.op == BinExprType.And:
            ret = (lhs & rhs)
        elif self.op == BinExprType.Or:
            ret = (lhs | rhs)
        elif self.op == BinExprType.Sll:
            ret = (lhs << rhs)
        elif self.op == BinExprType.Srl:
            ret = (lhs >> rhs)
        elif self.op == BinExprType.Xor:
            ret = (lhs ^ rhs)
        elif self.op == BinExprType.Not:
            ret = not (lhs)
        else:
            raise Exception("Unsupported binary expression type \"" + str(self.op) + "\"")
        
        return ret
    
    @staticmethod
    def mkCompositeEq(lhs, rhs):
        print("build_composite: " + str(type(lhs)))
        ret = None
        
        if isinstance(lhs, FieldCompositeModel):
            # Keep recursing

            for i in range(len(lhs.field_l)):
                lhs_f = lhs.field_l[i]
                rhs_f = rhs.field_l[i]
                sub = ExprBinModel.mkCompositeEq(lhs_f, rhs_f)
                if ret is None:
                    ret = sub
                elif sub is not None:
                    ret = ExprBinModel(sub, BinExprType.And, ret)
        elif isinstance(lhs, FieldScalarModel):
            ret = ExprBinModel(
                ExprFieldRefModel(lhs),
                BinExprType.Eq,
                ExprFieldRefModel(rhs))
                
        return ret        
