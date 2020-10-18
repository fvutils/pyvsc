'''
Created on Oct 17, 2020

@author: ballance
'''
import vsc
from vsc_test_case import VscTestCase

class TestSelect(VscTestCase):
    
    def test_distselect(self):
        hist = [0]*4
        
        for i in range(100):
            idx = vsc.distselect([1, 1, 10, 10])
            hist[idx] += 1
            
        print("hist: " + str(hist))
        self.assertGreater(hist[3], hist[0])
        self.assertGreater(hist[2], hist[1])
        
    def test_randselect(self):
        hist = [0]*4
        
        def task(idx):
            hist[idx] += 1

        for i in range(100):
            vsc.randselect([
                   (1, lambda: task(0)),
                   (1, lambda: task(1)),
                   (10, lambda: task(2)),
                   (10, lambda: task(3))])
        print("hist: " + str(hist))
        self.assertGreater(hist[3], hist[0])
        self.assertGreater(hist[2], hist[1])
        
        