'''
Created on Aug 4, 2019

@author: ballance
'''

class RangelistModel():
    
    def __init__(self, rl):
        self.range_l = []
        for r in rl:
            if isinstance(r, list):
                if len(r) == 2:
                    self.range_l.append([r[0], r[1]])
                else:
                    raise Exception("Each range element must have 2 elements")
            else:
                self.range_l.append([int(r), int(r)])
                
    
    def __contains__(self, val):
        for r in self.range_l:
            if val >= r[0] and val <= r[1]:
                return True
            
        return False
        