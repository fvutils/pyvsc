'''
Created on May 22, 2022

@author: mballance
'''
from vsc2.impl.rand_obj_impl import RandObjImpl

class RandObjDecoratorImpl(object):
    
    def __init__(self, kwargs):
        pass
    
    def __call__(self, T):
        
        RandObjImpl.addMethods(T)
        
        return T
    
    pass