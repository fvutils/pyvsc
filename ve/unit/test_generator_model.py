'''
Created on Mar 17, 2020

@author: ballance
'''
from unittest.case import TestCase

from vsc.model.coverage_options_model import CoverageOptionsModel
from vsc.model.covergroup_model import CovergroupModel
from vsc.model.coverpoint_bin_array_model import CoverpointBinArrayModel
from vsc.model.coverpoint_bin_collection_model import CoverpointBinCollectionModel
from vsc.model.coverpoint_cross_model import CoverpointCrossModel
from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.field_composite_model import FieldCompositeModel
from vsc.model.field_scalar_model import FieldScalarModel
from vsc.model.generator_model import GeneratorModel
from vsc.model.randomizer import Randomizer
from vsc.model.rangelist_model import RangelistModel
from vsc.model.source_info import SourceInfo


class TestGeneratorModel(TestCase):
    
    def test_smoke(self):
        stim = FieldCompositeModel("stim", True)
        f = FieldScalarModel("a", 16, False, True)
        stim.add_field(f)
        f2 = FieldScalarModel("b", 16, False, True)
        stim.add_field(f2)
        
        cg = CovergroupModel("cg")
        
        cp = CoverpointModel(ExprFieldRefModel(f), "cp1",
                             CoverageOptionsModel())
        cg.add_coverpoint(cp)
        bn = CoverpointBinArrayModel("cp", 0, 1, 16)
        cp.add_bin_model(bn)
        
        cp2 = CoverpointModel(ExprFieldRefModel(f2), "cp2",
                              CoverageOptionsModel())
        cg.add_coverpoint(cp2)
        bn = CoverpointBinArrayModel("cp", 0, 1, 16)
        cp2.add_bin_model(bn)
        
        gen = GeneratorModel("top")
        gen.add_field(stim)
        gen.add_covergroup(cg)
        
        gen.finalize()

        # Need a special randomizer to deal with generators        
        r = Randomizer()

        count = 0        
        for i in range(1000):
            r.do_randomize(SourceInfo("",-1), [gen])
            cg.sample()
            count += 1
            cov = cg.get_coverage()
            if cov == 100:
                break
            
        self.assertEqual(cg.get_coverage(), 100)
        # Ensure that we converge relatively quickly
        self.assertLessEqual(count, 32)

    def test_coverpoint_bins(self):
        stim = FieldCompositeModel("stim", True)
        f = FieldScalarModel("a", 16, False, True)
        stim.add_field(f)
        f2 = FieldScalarModel("b", 16, False, True)
        stim.add_field(f2)
        
        cg = CovergroupModel("cg")
        
        cp = CoverpointModel(ExprFieldRefModel(f), "cp1",
                             CoverageOptionsModel())
        cg.add_coverpoint(cp)
        cp.add_bin_model(CoverpointBinArrayModel("bn1", 0, 1, 16))
        cp.add_bin_model(CoverpointBinCollectionModel.mk_collection("bn2", RangelistModel([
            [17,65535-16-1]
            ]), 16))
        cp.add_bin_model(CoverpointBinArrayModel("bn3", 0, 65535-16, 65535))
        
        cp2 = CoverpointModel(ExprFieldRefModel(f2), "cp2",
                              CoverageOptionsModel())
        cg.add_coverpoint(cp2)
        bn = CoverpointBinArrayModel("cp", 0, 1, 16)
        cp2.add_bin_model(bn)
        
        gen = GeneratorModel("top")
        gen.add_field(stim)
        gen.add_covergroup(cg)
        
        gen.finalize()

        # Need a special randomizer to deal with generators        
        r = Randomizer()

        count = 0        
        for i in range(1000):
            r.do_randomize(SourceInfo("",-1), [gen])
            cg.sample()
            count += 1
            cov = cg.get_coverage()
            if cov == 100:
                break
            
        self.assertEqual(cg.get_coverage(), 100)
        # Ensure that we converge relatively quickly
        self.assertLessEqual(count, 64)

    def test_cross(self):
        stim = FieldCompositeModel("stim", True)
        f = FieldScalarModel("a", 16, False, True)
        stim.add_field(f)
        f2 = FieldScalarModel("b", 16, False, True)
        stim.add_field(f2)
        
        cg = CovergroupModel("cg")
        
        cp = CoverpointModel(ExprFieldRefModel(f), "cp1",
                             CoverageOptionsModel())
        cg.add_coverpoint(cp)
        bn = CoverpointBinArrayModel("cp", 0, 1, 16)
        cp.add_bin_model(bn)
        
        cp2 = CoverpointModel(ExprFieldRefModel(f2), "cp2",
                              CoverageOptionsModel())
        cg.add_coverpoint(cp2)
        bn = CoverpointBinArrayModel("cp", 0, 1, 16)
        cp2.add_bin_model(bn)
        
        cr = CoverpointCrossModel("aXb",
                                  CoverageOptionsModel())
        cr.add_coverpoint(cp)
        cr.add_coverpoint(cp2)
        cg.add_coverpoint(cr)
        
        gen = GeneratorModel("top")
        gen.add_field(stim)
        gen.add_covergroup(cg)
        
        gen.finalize()

        # Need a special randomizer to deal with generators        
        r = Randomizer()

        count = 0        
        for i in range(1000):
            r.do_randomize(SourceInfo("",-1), [gen])
            cg.sample()
            count += 1
            cov = cg.get_coverage()
            print("Coverage: (" + str(i) + ") " + str(cov))
            if cov == 100:
                break
            
        self.assertEqual(cg.get_coverage(), 100)
        # Ensure that we converge relatively quickly
        self.assertLessEqual(count, (256+16+16))

