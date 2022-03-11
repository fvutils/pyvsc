'''
Created on Feb 26, 2022

@author: mballance
'''

class ScalarT(object):
    W = 0
    S = False
    
    def __init__(self):
        raise Exception("Standalone creation of fields is not supported")