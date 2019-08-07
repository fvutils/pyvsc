'''
Created on Aug 3, 2019

@author: ballance
'''
from vsc.model.covergroup_model import CovergroupModel
from vsc.types import rangelist, bit_t, to_expr, type_base
from vsc.model.coverpoint_model import CoverpointModel
from vsc.impl.ctor import pop_expr
from vsc.model.rangelist_model import RangelistModel
from vsc.model.coverpoint_bin_model import CoverpointBinModel
from vsc.model.coverpoint_bin_array_model import CoverpointBinArrayModel
from vsc.model.coverpoint_bin_collection_model import CoverpointBinCollectionModel


# marks 
class covergroup():
    def __init__(self):
        self.model = None
        self.coverpoint_l = []
        self.cross_l = []
        
    def init_model(self):
        self.model = CovergroupModel()
        
        for cp_n in dir(self):
            cp_o = getattr(self, cp_n)
            if isinstance(cp_o, coverpoint):
                self.model.coverpoint_l.append(cp_o.build_model(cp_n))
   
        # Initialize the cross models second         
        for cp_n in dir(self):
            cp_o = getattr(self, cp_n)
            if isinstance(cp_o, cross):
                cp_o.init_model()
   
    
    def sample(self):
        '''
        Base sampling method that samples all coverpoints and crosses
        '''
        
        self.model.sample()
            
#         for cp_n in dir(self):
#             cp_o = getattr(self, cp_n)
#             if isinstance(cp_o, coverpoint):
#                 cp_o.sample()
            
            
        pass
    
    def dump(self, ind=""):
        self.model.dump(ind)


class bin():
    def __init__(self, *args):
        self.range_l = args
        
    def build_model(self, name, cp):
        # Construct a range model
        range_l = RangelistModel(self.range_l)
        return CoverpointBinModel(name, cp, range_l)
        

class bin_array():
    
    def __init__(self, nbins, *args):
        self.nbins = nbins
        self.range_l = args
    
    def build_model(self, name, cp):
        ret = CoverpointBinCollectionModel()
        
        # First, need to determine how many total bins
        # Construct a range model
        if len(self.nbins) == 0:
            # unlimited number of bins
            for r in self.range_l:
                if isinstance(r, list):
                    ret.bin_l.append(CoverpointBin)
                else:
                    pass
            return CoverpointBinArrayModel(name, cp, self.range_l)
            print("TODO: array-bin")
        else:
            # TODO: Calculate number of values
            # TODO: Calculate values per bin
            print("TODO: limited-value bins")
            pass

        return ret
        
class coverpoint():
   
    def __init__(self, target, iff=None, bins={}):
        self.have_var = False
        self.target = None
        self.model = None
        if isinstance(target, type_base):
            self.have_var = True
            self.target = target
#        elif isinstance(target, int_t)
        else:
            # should be an actual variable (?)
            to_expr(target)
            self.target = pop_expr()
            
        self.iff = iff
        self.bins = bins
    
    def build_model(self, name):
        bin_model_l = []
        for bname in self.bins.keys():
            binspec = self.bins[bname]
          
            if hasattr(binspec, "build_model"):
                bin_model_l.append(binspec.build_model(bname, self))
            else:
                raise Exception("Unknown bin specification \"" + str(binspec) + "\"")
                
        self.model = CoverpointModel(self, name, bin_model_l)
        return self.model
    
    def sample(self):
        pass
    
    def get_val(self):
        return self.target.get_val()
    
    def __le__(self, rhs):
        if self.have_var:
            self.target(rhs)
        else:
            raise Exception("Attempting to set value of non-variable coverpoint")
    
class cross():
    
    def __init__(self, target_l, bins={}):
        for t in target_l:
            if not isinstance(t, coverpoint):
                raise Exception("Cross target \"" + str(t) + "\" is not a coverpoint")
        self.target_l = target_l
        self.bins = bins
        
    def init_model(self):
        pass
        

# Coverpoint variable
my_coverpoint = coverpoint(bit_t(4), bins={
    "a" : bin(rangelist(1, 2, [4,5])),
    "b" : bin_array([], rangelist(1, 2, [8,15]))
    })

