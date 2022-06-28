'''
Created on Apr 15, 2022

@author: mballance
'''

class RandT(object):
    
    T = None
    
    def __new__(cls, field=None):
        
        print("RandT: field=%s" % str(field))
        
        if field is None:
            # Return an instance of the actual class
            ret = cls.T()
        else:
            ret = field
        
        # TODO: must propagate the knowledge that
        # this is a rand field
        ret._modelinfo.set_rand()
       
        print("rand return %s" % str(type(ret)))
        return ret