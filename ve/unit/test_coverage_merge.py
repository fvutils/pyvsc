'''
Created on Jan 5, 2021

@author: mballance
'''
import vsc
from vsc_test_case import VscTestCase
from vsc1.impl.coverage_registry import CoverageRegistry
#from ucis.merge.db_merger import DbMerger
from ucis.mem.mem_factory import MemFactory

class TestCoverageMerge(VscTestCase):
    

    def test_same_cg_same_cp(self):
        
        @vsc.covergroup
        class cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    val=vsc.uint32_t()
                    ))
                self.cp = vsc.coverpoint(self.val, bins={
                    "a" : vsc.bin_array([], [1,10])
                    })
                pass
            
        cg_i = cg()
        
        cg_i.sample(0)
        cg_i.sample(2)
        
        db1 = vsc.write_coverage_db("xx", "mem")
        
        CoverageRegistry.clear()
        
        cg_i.sample(3)
        cg_i.sample(4)
        
        db2 = vsc.write_coverage_db("xx", "mem")

#        merger = DbMerger()
        
#        merger.merge(db1)
#        merger.merge(db2)

#        dbm = MemFactory.create()
#        merger.result(dbm)
        
#        print("dbm=" + str(dbm))
        
        