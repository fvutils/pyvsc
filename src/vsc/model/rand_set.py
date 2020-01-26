'''
Created on Jan 22, 2020

@author: ballance
'''
from builtins import set

class RandSet():
    """Contains information about one set of related fields and constraints"""
    
    def __init__(self):
        self.field_s = set()
        self.constraint_s = set()
        
    def add_field(self, f):
        self.field_s.add(f)
        
    def fields(self):
        return self.field_s
        
    def add_constraint(self, c):
        self.constraint_s.add(c)
        
    def constraints(self):
        return self.constraint_s
        
        