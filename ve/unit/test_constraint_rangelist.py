'''
Created on Nov 19, 2021

@author: mballance
'''
from .vsc_test_case import VscTestCase

class TestConstraintRangelist(VscTestCase):
    
    def test_mutable_rangelist(self):
        import vsc
        import time
        
        @vsc.randobj
        class Selector():
            def __init__(self):
                self.availableList = vsc.rangelist((0,900))
                self.selectedList = vsc.rand_list_t(vsc.uint32_t(), 15)
        
            @vsc.constraint
            def available_c(self):
                with vsc.foreach(self.selectedList) as sel:
                    sel.inside(self.availableList)
        
            def getSelected(self):
                '''Returns a sorted list of selected integers.'''
                selected = []
                for resource in self.selectedList:
                    selected.append(int(resource))
                selected.sort()
                return selected
        
        
        selector = Selector()
        
        startTime = time.time()
        selector.randomize()
        endTime = time.time()
        print(f"Selected integers ({len(selector.selectedList)}:  {selector.getSelected()}")
        print(f"Calculation time:  {endTime - startTime} s")
        
        selector.availableList.extend([(900, 1000)])
        
        startTime = time.time()
        selector.randomize()
        endTime = time.time()
        print(f"Selected integers ({len(selector.selectedList)}:  {selector.getSelected()}")
        print(f"Calculation time:  {endTime - startTime} s")        
        
    def test_change_range(self):
        import vsc
        import time
        
        @vsc.randobj
        class Selector():
            def __init__(self):
                self.availableList = vsc.rangelist((0,900))
                self.selectedList = vsc.rand_list_t(vsc.uint32_t(), 15)
        
            @vsc.constraint
            def available_c(self):
                with vsc.foreach(self.selectedList) as sel:
                    sel.inside(self.availableList)
        
            def getSelected(self):
                '''Returns a sorted list of selected integers.'''
                selected = []
                for resource in self.selectedList:
                    selected.append(int(resource))
                selected.sort()
                return selected
        
        
        selector = Selector()
        
        startTime = time.time()
        selector.randomize()
        endTime = time.time()
        
        print(f"Selected integers ({len(selector.selectedList)}:  {selector.getSelected()}")
        print(f"Calculation time:  {endTime - startTime} s")
        for v in selector.selectedList:
            self.assertGreaterEqual(v, 0)
            self.assertLessEqual(v, 900)

        selector.availableList.clear()
        selector.availableList.extend([(1000, 2000)])
        
        startTime = time.time()
        selector.randomize()
        endTime = time.time()
        print(f"Selected integers ({len(selector.selectedList)}:  {selector.getSelected()}")
        print(f"Calculation time:  {endTime - startTime} s")            
        
        for v in selector.selectedList:
            self.assertGreaterEqual(v, 1000)
            self.assertLessEqual(v, 2000)

