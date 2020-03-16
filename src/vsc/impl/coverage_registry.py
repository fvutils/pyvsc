'''
Created on Mar 14, 2020

@author: ballance
'''
from typing import Dict, List
from vsc.model.covergroup_model import CovergroupModel

class CoverageRegistry(object):
    
    _inst = None
    
    def __init__(self):
        # Map of 'simple' typename to a list of specific covergroup 
        # implementations. Difference parameterizations are named
        # _1, _2, _3, etc
        self.covergroup_type_m : Dict[str, List[CovergroupModel]] = {}
        pass
    
    @staticmethod
    def inst():
        if CoverageRegistry._inst is None:
            CoverageRegistry._inst = CoverageRegistry()
            
        return CoverageRegistry._inst
    
    def types(self):
        return self.covergroup_type_m.keys()
    
    def instances(self, t):
        return self.covergroup_type_m[t]
    
    def register_cg(self, cg : CovergroupModel):
        cg_t : CovergroupModel = None
        
        # First, see if there's an existing entry
        if cg.name in self.covergroup_type_m.keys():
            # Okay, now we need to do some detailed comparison
            for cg_c in self.covergroup_type_m[cg.name]:
                if cg_c.equals(cg):
                    cg_t = cg_c
                    break
                
            if cg_t is None:
                # Okay, create a clone of the instance and give it a new name
                cg_t = cg.clone()
                cg_t.srcinfo_inst = None # Types do not have instance information
                cg_t.finalize()
                self.covergroup_type_m[cg.name].append(cg_t)
                n_cg = len(self.covergroup_type_m[cg.name])

                # Base covergroup type is called 'name', while derivatives
                # are labeled _1, _2, _3                
                cg_t.name = cg_t.name + "_" + str(n_cg)
                
        else:
            # No, nothing here yet
            cg_t = cg.clone()
            cg_t.srcinfo_inst = None # Types do not have instance information
            cg_t.finalize()
            self.covergroup_type_m[cg.name] = [cg_t]
            
        # Hook up the instance to the relevant type covergroup
        cg.type_cg = cg_t
        cg_t.cg_inst_l.append(cg)
        
    def covergroup_types(self):
        ret = []
        for name,cg_l in self.covergroup_type_m.items():
            ret.extend(cg_l)
            
        return ret
        
        
    def accept(self, v):
        for name,cg_l in self.covergroup_type_m.items():
            for cg in cg_l:
                cg.accept(v)
        
    
        
    

    
        
    
    