'''
Created on Oct 10, 2021

@author: mballance
'''
from vsc_test_case import VscTestCase
from enum import IntEnum, auto
#from coverage import covergroup

class TestCoverageIgnoreBins(VscTestCase):
    
    def test_smoke(self):
        import vsc
        
        
        @vsc.randobj
        class ignore_bins_test(object):
            def __init__(self):
                self.a = vsc.rand_int32_t()
                self.value = vsc.rand_bit_t(32)
        
        @vsc.covergroup
        class val_cg(object):
            def __init__(self):
                self.instr = None
                self.cp_val = vsc.coverpoint(lambda: self.instr.value[7:5],
                                    cp_t=vsc.bit_t(3), ignore_bins=dict(
                                       invalid_value=vsc.bin(0b101, 0b110)
                                    ))
                self.cp_a = vsc.coverpoint(lambda: self.instr.a, 
                                    cp_t=vsc.bit_t(32), ignore_bins=dict(
                                        invalid_a=vsc.bin(5, 3, 100, 124, 1110)
                                        )
                                    )
        
        
        test_obj = ignore_bins_test()
        val_cg_i = val_cg()
        for i in range(5):
            test_obj.randomize()
            print("a = {}, value = {}".format(test_obj.a, test_obj.value))
            val_cg_i.instr = test_obj
            val_cg_i.sample()
        vsc.report_coverage(details=True)
#        print("coverage: ", val_cg_i.get_coverage())

    def test_ignore_left_trim(self):
        import vsc
        
        
        @vsc.randobj
        class ignore_bins_test(object):
            def __init__(self):
                self.a = vsc.rand_int32_t()
                self.value = vsc.rand_bit_t(32)
        
        @vsc.covergroup
        class val_cg(object):
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t()
                    ))
                self.cp_val = vsc.coverpoint(self.a, bins=dict(
                                    rng_1=vsc.bin_array([4], [1,3], [4,6], [7,9], [10,12])
                                ),
                                ignore_bins=dict(
                                    invalid_value=vsc.bin(4)
                                ))
        
        test_obj = ignore_bins_test()
        val_cg_i = val_cg()

        # Note: bins are partitioned *after* removing excluded bins. This means
        # that 11 values are partitioned into 4 bins.
        # [1,2]
        # [3,5]
        # [6,7]
        # [8..12] 
        val_cg_i.sample(2)
        val_cg_i.sample(5)
        val_cg_i.sample(6)
        val_cg_i.sample(12)
        vsc.report_coverage(details=True)
        cvg_m = vsc.get_coverage_report_model()
        self.assertEqual(len(cvg_m.covergroups), 1)
        self.assertEqual(len(cvg_m.covergroups[0].coverpoints), 1)
        self.assertEqual(len(cvg_m.covergroups[0].coverpoints[0].bins), 4)
        self.assertEqual(len(cvg_m.covergroups[0].coverpoints[0].ignore_bins), 1)
        self.assertEqual(cvg_m.covergroups[0].coverpoints[0].bins[0].count, 1)
        self.assertEqual(cvg_m.covergroups[0].coverpoints[0].bins[1].count, 1)
        self.assertEqual(cvg_m.covergroups[0].coverpoints[0].bins[2].count, 1)
        self.assertEqual(cvg_m.covergroups[0].coverpoints[0].bins[3].count, 1)
        self.assertEqual(cvg_m.covergroups[0].coverpoints[0].ignore_bins[0].count, 0)
        
        val_cg_i.sample(4)
        cvg_m = vsc.get_coverage_report_model()
        self.assertEqual(cvg_m.covergroups[0].coverpoints[0].ignore_bins[0].count, 1)

    def test_enum_bins_autobin_exclude(self):
        import vsc

        class my_e(IntEnum):
            A = auto()
            B = auto()
            C = auto()
            D = auto()
            E = auto()
            F = auto()
            G = auto()
            H = auto()
        
        @vsc.randobj
        class ignore_bins_test(object):
            def __init__(self):
                self.v = vsc.rand_enum_t(my_e)
        
        @vsc.covergroup
        class val_cg(object):
            def __init__(self):
                self.with_sample(dict(
                    v=vsc.enum_t(my_e)))
                
                self.cp_v = vsc.coverpoint(self.v,
                                    ignore_bins=dict(
                                       ignore_1=vsc.bin(my_e.D),
                                       ignore_2=vsc.bin(my_e.H)
                                    ))
        
        test_obj = ignore_bins_test()
        val_cg_i = val_cg()
        
        # Sample all non-excluded values
        for v in (my_e.A, my_e.B, my_e.C, my_e.E, my_e.F, my_e.G):
            val_cg_i.sample(v)
            
        vsc.report_coverage(details=True)
        coverage_model = vsc.get_coverage_report_model()
        self.assertEqual(len(coverage_model.covergroups), 1)
        self.assertEqual(len(coverage_model.covergroups[0].coverpoints), 1)
        self.assertEqual(len(coverage_model.covergroups[0].coverpoints[0].bins), 6)
        self.assertEqual(len(coverage_model.covergroups[0].coverpoints[0].ignore_bins), 2)
        self.assertEqual(coverage_model.covergroups[0].coverpoints[0].ignore_bins[0].count, 0)
        self.assertEqual(coverage_model.covergroups[0].coverpoints[0].ignore_bins[1].count, 0)
        
        val_cg_i.sample(my_e.D)
        coverage_model = vsc.get_coverage_report_model()
        self.assertEqual(coverage_model.covergroups[0].coverpoints[0].ignore_bins[0].count, 1)
        self.assertEqual(coverage_model.covergroups[0].coverpoints[0].ignore_bins[1].count, 0)
        
        val_cg_i.sample(my_e.H)
        coverage_model = vsc.get_coverage_report_model()
        self.assertEqual(coverage_model.covergroups[0].coverpoints[0].ignore_bins[0].count, 1)
        self.assertEqual(coverage_model.covergroups[0].coverpoints[0].ignore_bins[1].count, 1)

    def test_enum_bins_autobin_exclude_illegal(self):
        import vsc

        class my_e(IntEnum):
            A = auto()
            B = auto()
            C = auto()
            D = auto()
            E = auto()
            F = auto()
            G = auto()
            H = auto()
        
        @vsc.randobj
        class ignore_bins_test(object):
            def __init__(self):
                self.v = vsc.rand_enum_t(my_e)
        
        @vsc.covergroup
        class val_cg(object):
            def __init__(self):
                self.with_sample(dict(
                    v=vsc.enum_t(my_e)))
                
                self.cp_v = vsc.coverpoint(self.v,
                                    ignore_bins=dict(
                                       ignore_1=vsc.bin(my_e.D)
                                    ),
                                    illegal_bins=dict(
                                       ignore_2=vsc.bin(my_e.H)
                                    ))
        
        test_obj = ignore_bins_test()
        val_cg_i = val_cg()
        
        # Sample all non-excluded values
        for v in (my_e.A, my_e.B, my_e.C, my_e.E, my_e.F, my_e.G):
            val_cg_i.sample(v)
            
        vsc.report_coverage(details=True)
        coverage_model = vsc.get_coverage_report_model()
        self.assertEqual(len(coverage_model.covergroups), 1)
        self.assertEqual(len(coverage_model.covergroups[0].coverpoints), 1)
        self.assertEqual(len(coverage_model.covergroups[0].coverpoints[0].bins), 6)
        self.assertEqual(len(coverage_model.covergroups[0].coverpoints[0].ignore_bins), 1)
        self.assertEqual(len(coverage_model.covergroups[0].coverpoints[0].illegal_bins), 1)
        self.assertEqual(coverage_model.covergroups[0].coverpoints[0].ignore_bins[0].count, 0)
        self.assertEqual(coverage_model.covergroups[0].coverpoints[0].illegal_bins[0].count, 0)
        
        val_cg_i.sample(my_e.D)
        coverage_model = vsc.get_coverage_report_model()
        self.assertEqual(coverage_model.covergroups[0].coverpoints[0].ignore_bins[0].count, 1)
        self.assertEqual(coverage_model.covergroups[0].coverpoints[0].illegal_bins[0].count, 0)
        
        val_cg_i.sample(my_e.H)
        coverage_model = vsc.get_coverage_report_model()
        self.assertEqual(coverage_model.covergroups[0].coverpoints[0].ignore_bins[0].count, 1)
        self.assertEqual(coverage_model.covergroups[0].coverpoints[0].illegal_bins[0].count, 1)

    def test_record_ignore(self):
        import sys
        import vsc
        from io import StringIO
        from ucis.xml.xml_factory import XmlFactory
        from ucis.report.text_coverage_report_formatter import TextCoverageReportFormatter
        from ucis.report.coverage_report_builder import CoverageReportBuilder

        @vsc.covergroup
        class cg_t(object):
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.int8_t()))
                self.cp = vsc.coverpoint(self.a, 
                    bins=dict(rng=vsc.bin_array([], [0,20])),
                    ignore_bins=dict(ignore=vsc.bin(0)))
                
        cg = cg_t()
        cg.sample(0)
        cg.sample(1)

        out = StringIO()
        vsc.write_coverage_db(out)
#        vsc.report_coverage(details=True)
        db = XmlFactory.read(StringIO(out.getvalue()))
        report = CoverageReportBuilder(db).build(db)
        # Confirm that the ignore bin was properly saved/restored
        self.assertEqual(
            len(report.covergroups[0].covergroups[0].coverpoints[0].ignore_bins), 1)
        reporter = TextCoverageReportFormatter(report, sys.stdout)
        reporter.details = True
        reporter.report()

    def test_ignore_single_val_bin(self):
        import sys
        import vsc
        from io import StringIO
        from ucis.xml.xml_factory import XmlFactory
        from ucis.report.text_coverage_report_formatter import TextCoverageReportFormatter
        from ucis.report.coverage_report_builder import CoverageReportBuilder

        @vsc.covergroup
        class cg_t(object):
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.int8_t()))
                self.cp = vsc.coverpoint(self.a, 
                    bins=dict(
                        ign=vsc.bin(0),
                        rng=vsc.bin_array([], [1,20])),
                    ignore_bins=dict(ignore=vsc.bin(0)))
                
        cg = cg_t()
        cg.sample(0)
        cg.sample(1)

        out = StringIO()
        vsc.write_coverage_db(out)
        vsc.report_coverage(details=True)
        db = XmlFactory.read(StringIO(out.getvalue()))
        report = CoverageReportBuilder(db).build(db)
        # Confirm that the ignore bin was properly saved/restored
        self.assertEqual(
            len(report.covergroups[0].covergroups[0].coverpoints[0].bins), 20)
        self.assertEqual(
            len(report.covergroups[0].covergroups[0].coverpoints[0].ignore_bins), 1)
        reporter = TextCoverageReportFormatter(report, sys.stdout)
        reporter.details = True
        reporter.report()

    # def test_ignore_full_array_bin(self):
    #     import sys
    #     import vsc
    #     from io import StringIO
    #     from ucis.xml.xml_factory import XmlFactory
    #     from ucis.report.text_coverage_report_formatter import TextCoverageReportFormatter
    #     from ucis.report.coverage_report_builder import CoverageReportBuilder

    #     @vsc.covergroup
    #     class cg_t(object):
    #         def __init__(self):
    #             self.with_sample(dict(
    #                 a=vsc.int8_t()))
    #             self.cp = vsc.coverpoint(self.a, 
    #                 bins=dict(
    #                     single=vsc.bin(0),
    #                     rng=vsc.bin_array([], [1,20])),
    #                 ignore_bins=dict(ignore=vsc.bin(1,20)))
                
    #     cg = cg_t()
    #     cg.sample(0)
    #     cg.sample(1)

    #     out = StringIO()
    #     vsc.write_coverage_db(out)
    #     vsc.report_coverage(details=True)
    #     db = XmlFactory.read(StringIO(out.getvalue()))
    #     report = CoverageReportBuilder(db).build(db)
    #     # Confirm that the ignore bin was properly saved/restored
    #     self.assertEqual(
    #         len(report.covergroups[0].covergroups[0].coverpoints[0].bins), 1)
    #     self.assertEqual(
    #         len(report.covergroups[0].covergroups[0].coverpoints[0].ignore_bins), 1)
    #     reporter = TextCoverageReportFormatter(report, sys.stdout)
    #     reporter.details = True
    #     reporter.report()

    # def test_example(self):
    #     import vsc
    #     DATA_WIDTH = 4

    #     @vsc.covergroup
    #     class my_covergroup(object):
    #         def __init__(self,a,b,op):      
    #             super().__init__()
    #             self.options.weight = 1
    #             self.operation_cvg = vsc.coverpoint(op,
    #                 bins={"Ops.ADD":vsc.bin(0), "Ops.SUB":vsc.bin(1), "Ops.NOT":vsc.bin(2), "Ops.NOR":vsc.bin(3), "Ops.NAND":vsc.bin(4), "Ops.AND":vsc.bin(5), "Ops.OR":vsc.bin(6), "Ops.XOR":vsc.bin(7)},
    #                 name="alu_op"
    #                 )
        
    #             self.operanda_cvg = vsc.coverpoint(a,
    #                 bins = {"illegal/ignore": vsc.bin(0), "low": vsc.bin_array([],[1,int(2**DATA_WIDTH/2)]), "high": vsc.bin_array([],[int(2**DATA_WIDTH/2)+1,2**DATA_WIDTH-1])}, 
    #                     options=dict(weight=2),
    #                     ignore_bins=dict(invalid_value=vsc.bin(1,2)),
    #                     name="alu_operand_a")
    #             self.operandb_cvg = vsc.coverpoint(b,
    #                     bins = {"low": vsc.bin_array([],[0,int(2**DATA_WIDTH/2)]), "high": vsc.bin_array([],[int(2**DATA_WIDTH/2)+1,2**DATA_WIDTH-1])}, 
    #                     name="alu_operand_b")
    #             self.cross_a_b = vsc.cross([self.operanda_cvg,self.operandb_cvg])


    #     a = 0
    #     b = 0
    #     op = 0
    #     cg = my_covergroup(lambda:a, lambda:b, lambda:op)
    #     for i in range(1,16):
    #         a = i
    #         b = i
    #         cg.sample()
    #     vsc.report_coverage(details=True)
    #     vsc.write_coverage_db("pyvsc_coverage_result.xml")

        