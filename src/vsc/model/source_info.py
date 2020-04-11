

# Created on Mar 13, 2020
#
# @author: ballance


class SourceInfo(object):
    
    def __init__(self, filename, lineno):
        self.filename = filename
        self.lineno = lineno
        
    def __str__(self):
        return self.filename + ":" + str(self.lineno)
    
    def clone(self):
        return SourceInfo(self.filename, self.lineno)
        