'''
Created on May 19, 2020

@author: ballance
'''
from vsc_test_case import VscTestCase
from vsc1.model.constraint_model import ConstraintModel
from vsc1.model.field_scalar_model import FieldScalarModel
from vsc1.model.constraint_if_else_model import ConstraintIfElseModel
from vsc1.model.constraint_implies_model import ConstraintImpliesModel
from vsc1.model.expr_bin_model import ExprBinModel
from vsc1.model.expr_fieldref_model import ExprFieldRefModel
from vsc1.model.bin_expr_type import BinExprType
from vsc1.model.constraint_scope_model import ConstraintScopeModel
from vsc1.model.expr_literal_model import ExprLiteralModel
from vsc1.visitors.model_pretty_printer import ModelPrettyPrinter
from vsc1.model.constraint_expr_model import ConstraintExprModel
from vsc1.model.constraint_block_model import ConstraintBlockModel
from vsc1.visitors.constraint_copy_builder import ConstraintCopyBuilder

class TestConstraintCopier(VscTestCase):
    
    def test_simple(self):
        a = FieldScalarModel("a", 16, False, True)
        b = FieldScalarModel("b", 16, False, True)
        c = FieldScalarModel("c", 16, False, True)
        l = ExprLiteralModel(10, False, 8)
        ab_c = ConstraintBlockModel("ab_c", [
            ConstraintImpliesModel(
                ExprBinModel(
                    ExprFieldRefModel(a),
                    BinExprType.Lt,
                    ExprFieldRefModel(b)
                ), [
                        ConstraintExprModel(
                            ExprBinModel(
                                ExprFieldRefModel(c),
                                BinExprType.Eq,
                                l)
                        )
                ]
            )
        ])
        
        copy = ConstraintCopyBuilder.copy(ab_c)
        self.assertEquals(1, len(copy))
        self.assertIsNot(ab_c, copy[0])
        