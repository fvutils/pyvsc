'''
Created on Feb 29, 2020

@author: ballance
'''

class RandObjModelIF(object):
    """Implements a callback interface to notify about randomization phases"""
    
    def pre_randomize(self):
        pass
    
    def post_randomize(self):
        pass