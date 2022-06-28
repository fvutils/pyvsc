'''
Created on Feb 26, 2022

@author: mballance
'''

from vsc2.impl.bit_t_meta import BitTMeta
from vsc2.impl.int_t_meta import IntTMeta
from vsc2.impl.scalar_t import ScalarT
from vsc2.impl.enum_t import EnumT
from vsc2.impl.enum_t_meta import EnumTMeta
from vsc2.impl.rand_t import RandT
from vsc2.impl.rand_t_meta import RandTMeta


class rand(RandT, metaclass=RandTMeta):
    # 'rand' must wrap any field to set 'rand' flag
    pass

def attr(T):
    raise Exception("attr used")

class enum_t(EnumT, metaclass=EnumTMeta):
    pass

class int_t(ScalarT, metaclass=IntTMeta):
    W = 32
    S = True
    
    
class bit_t(ScalarT, metaclass=BitTMeta):
    W = 1
    S = False
    pass

#********************************************************************
#* Compat types that match with vsc1
#********************************************************************

def rand_bit_t(w=1, i=0):
    return rand(bit_t(w, i))

def rand_int_t(w=32, i=0):
    return rand(int_t(w, i))

def rand_enum_t(e_t, i=0):
    return rand(enum_t(e_t))

rand_uint8_t = rand[bit_t[8]]
rand_uint16_t = rand[bit_t[16]]
rand_uint32_t = rand[bit_t[32]]
rand_uint64_t = rand[bit_t[64]]

rand_int8_t = rand[int_t[8]]
rand_int16_t = rand[int_t[16]]
rand_int32_t = rand[int_t[32]]
rand_int64_t = rand[int_t[64]]

uint8_t = bit_t[8]
uint16_t = bit_t[16]
uint32_t = bit_t[32]
uint64_t = bit_t[64]

int8_t = int_t[8]
int16_t = int_t[16]
int32_t = int_t[32]
int64_t = int_t[64]

def rand_attr(f):
    f._modelinfo.set_rand()
    return f

