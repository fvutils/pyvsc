'''
Created on Feb 29, 2020

@author: ballance
'''

class CoverpointFacadeIF(object):
    """Specifies the API a coverpoint user-side facade object is expected to implement"""
    
    def get_val(self, cp_m : 'CoverpointModel') -> int:
        raise NotImplementedError()
        