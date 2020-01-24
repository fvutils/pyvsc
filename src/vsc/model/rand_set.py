'''
Created on Jan 22, 2020

@author: ballance
'''

class RandSet():
    """Contains information about one set of related fields and constraints"""
    
    def __init__(self):
        self.field_l = []
        self.constraint_l = []
        
    def add_field(self, f):
        self.field_l.append(f)
        
    def fields(self):
        return self.field_l
        
    def add_constraint(self, c):
        self.constraint_l.append(c)
        
    def constraints(self):
        return self.constraint_l
        
        