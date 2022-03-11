'''
Created on Feb 26, 2022

@author: mballance
'''

from typing import Generic, TypeVar

from vsc2.impl.bit_t_meta import BitTMeta
from vsc2.impl.int_t_meta import IntTMeta
from vsc2.impl.scalar_t import ScalarT
from vsc2.impl.enum_t import EnumT
from vsc2.impl.enum_t_meta import EnumTMeta


T = TypeVar('T')

class rand(Generic[T]):
    pass

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
#* Compat types with vsc1
#********************************************************************
rand_uint8_t = rand[bit_t[8]]
rand_uint16_t = rand[bit_t[16]]
rand_uint32_t = rand[bit_t[32]]
rand_uint64_t = rand[bit_t[64]]

rand_int8_t = rand[int_t[8]]
rand_int16_t = rand[int_t[16]]
rand_int32_t = rand[int_t[32]]
rand_int64_t = rand[int_t[64]]


