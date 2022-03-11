'''
Created on Feb 27, 2022

@author: mballance
'''

class EnumTMeta(type):
    
    def __init__(self, name, bases, dct):
        self.type_m = {}
        
    def __getitem__(self, item):
        pass
    
