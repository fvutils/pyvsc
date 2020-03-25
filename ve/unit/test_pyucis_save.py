'''
Created on Mar 14, 2020

@author: ballance
'''

from ucis.lib import libucis
from ucis.lib.lib_ucis import LibUCIS
from unittest import TestCase

import vsc
from vsc.impl import ctor
from vsc.visitors.ucis.coverage_save_visitor import CoverageSaveVisitor
from ucis.lib.LibFactory import LibFactory
from ucis.test_data import TestData
from ucis import UCIS_TESTSTATUS_OK
from vsc.impl.coverage_registry import CoverageRegistry
from ucis.mem.mem_factory import MemFactory
from ucis.xml.xml_writer import XmlWriter
from _io import StringIO
from ucis.xml.xml_reader import XmlReader


class TestPyUcisSave(TestCase):
    
    def setUp(self):
        ctor.test_setup()
        
    def tearDown(self):
        ctor.test_teardown()
    
    def test_simple_dump(self):
        
        @vsc.covergroup
        class my_covergroup(object):
            
            def __init__(self):
                
                self.with_sample(dict(
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t()
                    ))
                
                self.a_cp = vsc.coverpoint(self.a, bins=dict(
                    a_bins =  vsc.bin_array([], [1,8])
                    ))
                
                self.b_cp = vsc.coverpoint(self.b, bins=dict(
                    b_bins = vsc.bin_array([], [1,8])
                    ))

        cg_1 = my_covergroup()
        
        cg_1.sample(1, 2)
        cg_1.sample(2, 1)
        cg_1.sample(4, 2)
        
        cg_2 = my_covergroup()
        
        cg_2.sample(5, 4)
        cg_2.sample(6, 2)
        cg_2.sample(7, 8)

        db = MemFactory.create()
        v = CoverageSaveVisitor(db)

        td = TestData(
            teststatus=UCIS_TESTSTATUS_OK,
            toolcategory="UCIS:simulator",
            date="20200101132000")        
        v.save(td, CoverageRegistry.inst().covergroup_types())
        db.close()

        out = StringIO()        
        writer = XmlWriter()
        writer.write(out, db)

        print("Output:\n" + out.getvalue())        

        xmlin = StringIO(out.getvalue())        
        XmlReader.validate(xmlin)
        

        