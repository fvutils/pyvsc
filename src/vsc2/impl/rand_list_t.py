'''
Created on Jun 28, 2022

@author: mballance
'''
from vsc2.impl.list_t import ListT


class RandListT(object):
    
    def __new__(cls, t=None, sz=0):
        if t is None:
            ret = cls.T()
        else:
            ret = ListT(t, sz)

        ret._modelinfo.set_rand()
        
        return ret