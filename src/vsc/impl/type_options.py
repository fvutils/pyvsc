'''
Created on Feb 7, 2020

@author: ballance
'''

class TypeOptions():
    
    def __init__(self):
        self.locked = False
        self.weight = 1
        self.goal = 100
        self.comment = ""
        self.merge_instances = False
        self.distribute_first = False
        
    def set(self, values):
        for key in values.keys():
            if not hasattr(self, key):
                raise AttributeError("Option %s is invalid" % (key))
            setattr(self, key, values[key])
    
    def __setattr__(self, field, val):
        if field == "locked" and hasattr(self, "locked") and self.locked:
            raise Exception("Failed to set option \"%s\" since covergroup is locked" % (field))
        object.__setattr__(self, field, val)
        
    def _lock(self):
        self.locked = True
        