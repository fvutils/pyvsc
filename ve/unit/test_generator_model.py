'''
Created on Mar 17, 2020

@author: ballance
'''
from unittest.case import TestCase
from vsc.model.composite_field_model import CompositeFieldModel
from vsc.model.generator_model import GeneratorModel
from vsc.model.covergroup_model import CovergroupModel
from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.coverpoint_bin_array_model import CoverpointBinArrayModel
from vsc.model.scalar_field_model import ScalarFieldModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.randomizer import Randomizer

class TestGeneratorModel(TestCase):
    
    def test_smoke(self):
        stim = CompositeFieldModel("stim", True)
        f = ScalarFieldModel("a", 16, False, True)
        stim.add_field(f)
        
        cg = CovergroupModel("cg")
        cp = CoverpointModel(ExprFieldRefModel(f), "cp")
        cg.add_coverpoint(cp)
        bn = CoverpointBinArrayModel("cp", 1, 16)
        cp.add_bin_model(bn)
        
        gen = GeneratorModel("top")
        gen.add_field(stim)
        gen.add_covergroup(cg)
        
        gen.finalize()

        # Need a special randomizer to deal with generators        
        r = Randomizer()
        
        for i in range(5):
            r.do_randomize([gen])
            print("a=" + hex(f.val))
            cg.sample()
