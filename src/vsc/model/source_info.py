import sys


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
    
    @classmethod
    def mk(cls, levels=1):
        # sys._getframe is O(1). inspect.stack() would build FrameInfo for the
        # whole stack, reading source for every frame and, for a frame with no
        # source file, scanning all of sys.modules -- per call.
        try:
            frame = sys._getframe(levels+1)
        except ValueError:
            raise Exception("requested stack frame %d out-of-bounds" % levels)
        
        return cls(frame.f_code.co_filename, frame.f_lineno)
    
    @staticmethod
    def toString(srcinfo):
        if srcinfo is not None:
            return "%s:%d" % (srcinfo.filename, srcinfo.lineno)
        else:
            return "<unknown>"
        
