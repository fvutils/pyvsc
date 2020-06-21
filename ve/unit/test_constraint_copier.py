'''
Created on May 19, 2020

@author: ballance
'''
from vsc_test_case import VscTestCase
from vsc.model.constraint_model import ConstraintModel
from vsc.model.field_scalar_model import FieldScalarModel
from vsc.model.constraint_if_else_model import ConstraintIfElseModel
from vsc.model.constraint_implies_model import ConstraintImpliesModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.bin_expr_type import BinExprType
from vsc.model.constraint_scope_model import ConstraintScopeModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.visitors.model_pretty_printer import ModelPrettyPrinter
from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.visitors.constraint_copy_builder import ConstraintCopyBuilder

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
        
        print("Model: " + ModelPrettyPrinter.print(ab_c))
        copy = ConstraintCopyBuilder.copy(ab_c)
        self.assertEquals(1, len(copy))
        self.assertIsNot(ab_c, copy[0])
        print("Copy: " + ModelPrettyPrinter.print(copy[0]))
        