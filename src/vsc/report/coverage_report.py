'''
Created on Mar 25, 2020

@author: ballance
'''
from typing import List


class CoverageReport(object):
    """Coverage report in object-model form. Converted to text for display"""
    
    def __init__(self):
        self.covergroups : List['CoverageReport.Covergroup'] = []
        
    class Coveritem(object):
        
        def __init__(self, name):
            self.name = name
            self.coverage = 0.0
    
    class Covergroup(Coveritem):
        
        def __init__(self, name : str, is_type : bool):
            CoverageReport.Coveritem.__init__(self, name)
            self.is_type = is_type
            self.covergroups = []
            self.coverpoints = []
            self.crosses = []
            
    class Coverpoint(Coveritem):
        
        def __init__(self, name : str):
            CoverageReport.Coveritem.__init__(self, name)
            self.bins = []
            
    class Coverbin(Coveritem):
        
        def __init__(self, name : str, n_hits):
            CoverageReport.Coveritem.__init__(self, name)
            self.n_hits = n_hits
            