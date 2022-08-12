'''
Created on May 17, 2020

@author: ballance
'''
from .vsc_test_case import VscTestCase
from vsc1.model.field_composite_model import FieldCompositeModel
from vsc1.model.field_array_model import FieldArrayModel
from vsc1.model.constraint_foreach_model import ConstraintForeachModel
from vsc1.model.constraint_block_model import ConstraintBlockModel
from vsc1.model.expr_bin_model import ExprBinModel
from vsc1.model.expr_array_subscript_model import ExprArraySubscriptModel
from vsc1.model.expr_fieldref_model import ExprFieldRefModel
from vsc1.model.bin_expr_type import BinExprType
from vsc1.model.expr_literal_model import ExprLiteralModel
from vsc1.model.randomizer import Randomizer
from vsc1.visitors.array_constraint_builder import ArrayConstraintBuilder
from vsc1.visitors.model_pretty_printer import ModelPrettyPrinter
from vsc1.model.constraint_expr_model import ConstraintExprModel
from vsc1.model.field_scalar_model import FieldScalarModel
from vsc1.visitors.constraint_override_rollback_visitor import ConstraintOverrideRollbackVisitor
from vsc1.model.constraint_implies_model import ConstraintImpliesModel
from vsc1.model.source_info import SourceInfo
from vsc1.model.rand_state import RandState

class TestScalarArrayModel(VscTestCase):
    
    def test_smoke(self):
        obj = FieldCompositeModel("obj")
        arr = obj.add_field(FieldArrayModel(
            "arr", 
            None, # type_t
            True,
            None, # not an enum-type 
            32, 
            False, 
            True, 
            True))
#         for i in range(10):
#             arr.add_field()
        obj.add_constraint(ConstraintBlockModel("XX", [
            ConstraintExprModel(
                ExprBinModel(
                    ExprFieldRefModel(arr.size),
                    BinExprType.Eq,
                    ExprLiteralModel(10, False, 32)))
            ]))
            
        foreach = ConstraintForeachModel(ExprFieldRefModel(arr))
        foreach.addConstraint(
            ConstraintExprModel(
                ExprBinModel(
                    ExprArraySubscriptModel(
                        ExprFieldRefModel(arr),
                        ExprFieldRefModel(foreach.index)),
                    BinExprType.Lt,
                    ExprLiteralModel(10, False, 32)
                    )
                )
            )
        
        obj.add_constraint(ConstraintBlockModel("c", [
            foreach
            ]))

#         print("Object: " + ModelPrettyPrinter.print(obj))
#                 
#         constraints = ArrayConstraintBuilder.build(obj)
#         for c in constraints:
#             print("Constraint: " + ModelPrettyPrinter.print(c))
#         print("Object(1): " + ModelPrettyPrinter.print(obj))
#         
#         ConstraintOverrideRollbackVisitor.rollback(obj)
#         print("Object(2): " + ModelPrettyPrinter.print(obj))
        randstate = RandState(0)        
        Randomizer.do_randomize(randstate, SourceInfo("", -1), [obj])
        
        for f in arr.field_l:
            print("" + f.name + ": " + str(int(f.get_val())))

    def test_incr(self):
        obj = FieldCompositeModel("obj")
        arr = obj.add_field(FieldArrayModel(
            "arr", 
            None, # type_t
            True, # is_scalar
            None, # not an enum-type list
            32, 
            False, 
            True, 
            False))
        for i in range(10):
            arr.add_field()
        obj.add_constraint(ConstraintBlockModel("XX", [
            ConstraintExprModel(
                ExprBinModel(
                    ExprFieldRefModel(arr.size),
                    BinExprType.Eq,
                    ExprLiteralModel(10, False, 32)))
            ]))
        foreach = ConstraintForeachModel(ExprFieldRefModel(arr))
        foreach.addConstraint(
            ConstraintImpliesModel(
                ExprBinModel(
                    ExprFieldRefModel(foreach.index),
                    BinExprType.Gt,
                    ExprLiteralModel(0, False, 32)), [
                        ConstraintExprModel(
                            ExprBinModel(
                                ExprArraySubscriptModel(
                                    ExprFieldRefModel(arr),
                                    ExprFieldRefModel(foreach.index)),
                                BinExprType.Eq,
                                ExprBinModel(
                                    ExprArraySubscriptModel(
                                        ExprFieldRefModel(arr),
                                        ExprBinModel(
                                            ExprFieldRefModel(foreach.index),
                                            BinExprType.Sub,
                                            ExprLiteralModel(1, False, 32))),
                                    BinExprType.Add,
                                    ExprLiteralModel(1, False, 32))
                                )
                            )
                        ]
                    )
                )
        
        obj.add_constraint(ConstraintBlockModel("c", [
            foreach
            ]))

#         print("Object: " + ModelPrettyPrinter.print(obj))
#                 
#         constraints = ArrayConstraintBuilder.build(obj)
#         for c in constraints:
#             print("Constraint: " + ModelPrettyPrinter.print(c))
#         print("Object(1): " + ModelPrettyPrinter.print(obj))
#         
#         ConstraintOverrideRollbackVisitor.rollback(obj)
#         print("Object(2): " + ModelPrettyPrinter.print(obj))
        randstate = RandState(0) 
        Randomizer.do_randomize(randstate, SourceInfo("",-1), [obj])
        
        for f in arr.field_l:
            print("" + f.name + ": " + str(int(f.get_val())))            

        