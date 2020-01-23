'''
Created on Jan 22, 2020

@author: ballance
'''

class RandInfo():
    """Contains information about a set of variables and constraints"""
    
    def __init__(self, randset_l, unconstrained_l, floating_constraint_l = []):
        self.randset_l = randset_l
        self.unconstrained_l = unconstrained_l
        self.floating_constraint_l = floating_constraint_l
        
    def add_randset(self, r):
        self.randset_l.append(r)
        
    def add_field(self, f):
        self.unconstrained_l.append(f)
        