'''
Created on Jun 23, 2022

@author: mballance
'''

class SampleMetaT(type):
    
    def __init__(self, name, bases, dct):
        pass
    
    def __getitem__(self, *args, **kwargs):
        print("item: (%s) (%s)" % (
            str(args), str(kwargs)))