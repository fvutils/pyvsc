'''
Created on Feb 29, 2020

@author: ballance
'''
from unittest.case import TestCase

from vsc.model.bin_expr_type import BinExprType
from vsc.model.composite_field_model import CompositeFieldModel
from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.randomizer import Randomizer
from vsc.model.scalar_field_model import FieldScalarModel
from vsc.model.value_scalar import ValueScalar
from vsc_test_case import VscTestCase


class TestRandModel(VscTestCase):
    
    def test_smoke(self):
        obj = CompositeFieldModel("obj")
        a = obj.add_field(FieldScalarModel("a", 8, False, True))
        b = obj.add_field(FieldScalarModel("a", 8, False, True))
        obj.add_constraint(ConstraintBlockModel("c", [
            ConstraintExprModel(
                ExprBinModel(
                    a.expr(),
                    BinExprType.Lt,
                    b.expr()))
            ]))
        
        rand = Randomizer()
        
        rand.do_randomize([obj])

        self.assertLess(a.val, b.val)

    def test_wide_var(self):
        obj = CompositeFieldModel("obj")
        a = obj.add_field(FieldScalarModel("a", 1024, False, True))
        obj.add_constraint(ConstraintBlockModel("c", [
            ConstraintExprModel(
                ExprBinModel(
                    a.expr(),
                    BinExprType.Gt,
                    ExprLiteralModel(0x80000000000000000, False, 72)
                    )
                )
            ]))
        
        rand = Randomizer()
        
        rand.do_randomize([obj])

        print("a=" + hex(int(a.val)))
        self.assertGreater(a.val, ValueScalar(0x80000000000000000))
        