# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# Created on Jul 23, 2019
#
# @author: ballance


from enum import IntEnum, Enum, EnumMeta

from vsc.impl.ctor import push_expr, pop_expr, in_constraint_scope
from vsc.impl.enum_info import EnumInfo
from vsc.impl.expr_mode import get_expr_mode
from vsc.model.bin_expr_type import BinExprType
from vsc.model.enum_field_model import EnumFieldModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_in_model import ExprInModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.expr_partselect_model import ExprPartselectModel
from vsc.model.expr_range_model import ExprRangeModel
from vsc.model.expr_rangelist_model import ExprRangelistModel
from vsc.model.scalar_field_model import FieldScalarModel
from vsc.model.value_scalar import ValueScalar
from vsc.model.field_scalar_array_model import FieldScalarArrayModel


def unsigned(v, w=-1):
    if w == -1:
        w = 32
    return expr(ExprLiteralModel(v, False, w))

def signed(v, w=-1):
    if w == -1:
        w = 32
    return expr(ExprLiteralModel(v, True, w))

class expr(object):
    def __init__(self, em):
        push_expr(em)
        self.em = em
        
    def bin_expr(self, op, rhs):
        to_expr(rhs)
       
        rhs_e = pop_expr()
        lhs_e = pop_expr()
        
        e = ExprBinModel(lhs_e, op, rhs_e)
        
        return expr(e)        
        
    def __eq__(self, rhs):
        return self.bin_expr(BinExprType.Eq, rhs)
    
    def __ne__(self, rhs):
        return self.bin_expr(BinExprType.Ne, rhs)
    
    def __le__(self, rhs):
        return self.bin_expr(BinExprType.Le, rhs)
    
    def __lt__(self, rhs):
        return self.bin_expr(BinExprType.Lt, rhs)
    
    def __ge__(self, rhs):
        return self.bin_expr(BinExprType.Ge, rhs)
    
    def __gt__(self, rhs):
        return self.bin_expr(BinExprType.Gt, rhs)
    
    def __add__(self, rhs):
        return self.bin_expr(BinExprType.Add, rhs)
    
    def __sub__(self, rhs):
        return self.bin_expr(BinExprType.Sub, rhs)
    
    def __truediv__(self, rhs):
        return self.bin_expr(BinExprType.Div, rhs)
    
    def __floordiv__(self, rhs):
        return self.bin_expr(BinExprType.Div, rhs)
    
    def __mul__(self, rhs):
        return self.bin_expr(BinExprType.Mul, rhs)
    
    def __mod__(self, rhs):
        return self.bin_expr(BinExprType.Mod, rhs)
    
    def __and__(self, rhs):
        return self.bin_expr(BinExprType.And, rhs)
    
    def __or__(self, rhs):
        return self.bin_expr(BinExprType.Or, rhs)
    
    def __xor__(self, rhs):
        return self.bin_expr(BinExprType.Xor, rhs)
    
    def __lshift__(self, rhs):
        return self.bin_expr(BinExprType.Sll, rhs)
    
    def __rshift__(self, rhs):
        return self.bin_expr(BinExprType.Srl, rhs)
    
    def __neg__(self):
        return self.bin_expr(BinExprType.Not, rhs)    
        
class rangelist(object):
    
    def __init__(self, *args):
        if len(args) == 0:
            raise Exception("Empty rangelist specified")

        self.range_l = ExprRangelistModel()
        for i in range(-1,-(len(args)+1), -1):
            a = args[i]
            if isinstance(a, list):
                # This needs to be a two-element array
                if len(a) != 2:
                    raise Exception("Range specified with " + str(len(a)) + " elements is invalid. Two elements required")
                to_expr(a[0])
                to_expr(a[1])
                e1 = pop_expr()
                e0 = pop_expr()
                self.range_l.add_range(ExprRangeModel(e0, e1))
            else:
                to_expr(a)
                e = pop_expr()
                self.range_l.add_range(e)
#            self.range_l.rl.reverse()

                # This needs to be convertioble to a
            
    def __contains__(self, lhs):
        to_expr(lhs)
        return expr(ExprInModel(pop_expr(), self.range_l))

def to_expr(t):
    if isinstance(t, expr):
        return t
    elif type(t) == int:
        return expr(ExprLiteralModel(t, True, 32))
    elif isinstance(type(t), (EnumMeta,IntEnum)):
        return expr(EnumInfo.get(type(t)).e2e(t))
    elif hasattr(t, "to_expr"):
        return t.to_expr()
    elif callable(t):
        raise Exception("TODO: support lambda references")
    else:
        print("Type: " + str(t) + " " + str(type(t)))
        raise Exception("Element \"" + str(t) + "\" isn't recognized, and doesn't provide to_expr")
    
    
class field_info(object):
    """Model-specific information about the field"""
    def __init__(self):
        self.id = -1
        self.name = None
        self.is_rand = False
        self.model = None
        
    def set_is_rand(self, is_rand):
        self.is_rand = is_rand
        if self.model is not None:
            self.model.is_declared_rand = is_rand
        
class type_base(object):
    """Base type for all primitive-type fields that participate in constraints"""
    
    def __init__(self, width, is_signed, i=0):
        self.width = width
        self.is_signed = is_signed
        self.val = i
        self._int_field_info = field_info()
        
    def get_model(self):
        if self._int_field_info.model is None:
            raise Exception("Field hasn't yet been constructed")
        return self._int_field_info.model
        
    def build_field_model(self, name):
        self._int_field_info.name = name
        self._int_field_info.model = FieldScalarModel(
            name,
            self.width,
            self.is_signed,
            self._int_field_info.is_rand,
            self
        )
        return self._int_field_info.model
    
    def do_pre_randomize(self):
        self._int_field_info.model.set_val(self.val)
    
    def do_post_randomize(self):
        self.val = self._int_field_info.model.get_val()
        
    def to_expr(self):
        return expr(ExprFieldRefModel(self._int_field_info.model))
#        return expr(self._int_field_info.model.get_indexed_fieldref_expr())
    
    def get_val(self):
        return int(self._int_field_info.model.get_val())
    
    def set_val(self, val):
        self._int_field_info.model.set_val(ValueScalar(int(val)))
        
#     def _get_val(self):
#         return int(self._int_field_info.model.get_val())
#     
#     def _set_val(self, val):
#         self.val = val
    
    def bin_expr(self, op, rhs):
        to_expr(rhs)
       
        push_expr(ExprFieldRefModel(self._int_field_info.model))

        lhs_e = pop_expr()
        rhs_e = pop_expr()
        
        e = ExprBinModel(lhs_e, op, rhs_e)
        
        return expr(e)

    def __eq__(self, rhs):
        return self.bin_expr(BinExprType.Eq, rhs)
    
    def __ne__(self, rhs):
        return self.bin_expr(BinExprType.Ne, rhs)
    
    def __le__(self, rhs):
        return self.bin_expr(BinExprType.Le, rhs)
    
    def __lt__(self, rhs):
        return self.bin_expr(BinExprType.Lt, rhs)
    
    def __ge__(self, rhs):
        return self.bin_expr(BinExprType.Ge, rhs)
    
    def __gt__(self, rhs):
        return self.bin_expr(BinExprType.Gt, rhs)
    
    def __add__(self, rhs):
        return self.bin_expr(BinExprType.Add, rhs)
    
    def __sub__(self, rhs):
        return self.bin_expr(BinExprType.Sub, rhs)
    
    def __truediv__(self, rhs):
        return self.bin_expr(BinExprType.Div, rhs)
    
    def __floordiv__(self, rhs):
        return self.bin_expr(BinExprType.Div, rhs)
    
    def __mul__(self, rhs):
        return self.bin_expr(BinExprType.Mul, rhs)
    
    def __mod__(self, rhs):
        return self.bin_expr(BinExprType.Mod, rhs)
    
    def __and__(self, rhs):
        return self.bin_expr(BinExprType.And, rhs)
    
    def __or__(self, rhs):
        return self.bin_expr(BinExprType.Or, rhs)
    
    def __xor__(self, rhs):
        return self.bin_expr(BinExprType.Xor, rhs)
    
    def __lshift__(self, rhs):
        return self.bin_expr(BinExprType.Sll, rhs)
    
    def __rshift__(self, rhs):
        return self.bin_expr(BinExprType.Srl, rhs)
    
    def __neg__(self):
        return self.bin_expr(BinExprType.Not, rhs)
        
    def __getitem__(self, val):
        if isinstance(val, slice):
            # slice
            to_expr(val.start)
            to_expr(val.stop)
            e0 = pop_expr()
            e1 = pop_expr()
            return expr(ExprPartselectModel(
                ExprFieldRefModel(self._int_field_info.model), e0, e1))
        else:
            # single value
            to_expr(val)
            e = pop_expr()
            return expr(ExprPartselectModel(
                ExprFieldRefModel(self._int_field_info.model), e))
        
    def clone(self):
        return type_base(self.width, self.is_signed)

class type_bool(type_base):
    """Base class for boolean fields"""
    
    def __init__(self, i=False):
        super().__init__(1, False, 1 if i else 0)
        
    def build_field_model(self, name):
        # If we have an IntEnum, then collect the values
        self._int_field_info.name = name
        self._int_field_info.model = EnumFieldModel(
            name,
            self.enum_i.enums,
            self._int_field_info.is_rand
        )
        return self._int_field_info.model        
        
    def get_val(self):
        """Gets the field value"""
        return bool(self._int_field_info.model.get_val())
    
    def set_val(self, val):
        """Sets the field value"""
        self._int_field_info.model.set_val(bool(val))

class type_enum(type_base):
    """Base class for enumerated-type fields"""
    
    def __init__(self, t, i=None):
        # TODO: determine size of enum
        self.enum_i = EnumInfo.get(t)

        width = 32
        is_signed = True
        
        super().__init__(width, is_signed, i)

        # The value of an enum field is stored in two ways
        # The enum_id is the index into the enum type
        # The 'val' field is the actual enum value        
        self.enum_id = 0
        if i is not None:
            # TODO
#            self.enum_id = list(t).f
            pass
        
    def build_field_model(self, name):
        # If we have an IntEnum, then collect the values
                
        self._int_field_info.name = name
        self._int_field_info.model = EnumFieldModel(
            name,
            self.enum_i.enums,
            self._int_field_info.is_rand
        )
        return self._int_field_info.model        
        
    def get_val(self):
        """Returns the enum id"""
        return self.enum_i.v2e(self._int_field_info.model.get_val())
    
    def set_val(self, val):
        """Sets the enum id"""
        self._int_field_info.model.set_val(self.enum_i.ev2(val))
    
class enum_t(type_enum):
    """Creates a non-random enumerated-type attribute"""
    
    def __init__(self, t, i=None):
        super().__init__(t, i)
        
class rand_enum_t(enum_t):
    """Creates a random enumerated-type attribute"""
    
    def __init__(self, t, i=None):
        super().__init__(t, i)
        self._int_field_info.is_rand = True
        
class bit_t(type_base):
    """Creates an unsigned arbitrary-width attribute"""
    def __init__(self, w=1, i=0):
        super().__init__(w, False, i)
        
class bool_t(type_base):
    """Creates a boolean field"""
    def __init__(self, i=False):
        super.__init__(1, False, 1 if i else 0)

class uint8_t(bit_t):
    """Creates an unsigned 8-bit attribute"""
    def __init__(self, i=0):
        super().__init__(8, i)
        
class uint16_t(bit_t):
    """Creates an unsigned 16-bit attribute"""
    def __init__(self, i=0):
        super().__init__(16, i)
        
class uint32_t(bit_t):
    """Creates an unsigned 32-bit attribute"""
    def __init__(self, i=0):
        super().__init__(32, i)
        
class uint64_t(bit_t):
    """Creates an unsigned 64-bit attribute"""
    def __init__(self, i=0):
        super().__init__(64, i)

class rand_bit_t(bit_t):
    """Creates a random unsigned arbitrary-width attribute"""
    
    def __init__(self, w=1, i=0):
        super().__init__(w, i)
        self._int_field_info.is_rand = True
        
class rand_uint8_t(rand_bit_t):
    """Creates a random unsigned 8-bit attribute"""
    def __init__(self, i=0):
        super().__init__(8, i)
        
class rand_uint16_t(rand_bit_t):
    """Creates a random unsigned 16-bit attribute"""
    def __init__(self, i=0):
        super().__init__(16, i)
        
class rand_uint32_t(rand_bit_t):
    """Creates a random unsigned 32-bit attribute"""
    def __init__(self, i=0):
        super().__init__(32, i)
        
class rand_uint64_t(rand_bit_t):
    """Creates a random unsigned 64-bit attribute"""
    def __init__(self, i=0):
        super().__init__(64, i)
        
class int_t(type_base):
    """Creates a signed arbitrary-width attribute"""
    
    def __init__(self, w=32, i=0):
        super().__init__(w, True, i)
        
class int8_t(int_t):
    """Creates a signed 8-bit attribute"""
    def __init__(self, i=0):
        super().__init__(8, i)
        
class int16_t(int_t):
    """Creates a signed 16-bit attribute"""
    def __init__(self, i=0):
        super().__init__(16, i)
        
class int32_t(int_t):
    """Creates a signed 32-bit attribute"""
    def __init__(self, i=0):
        super().__init__(32, i)
        
class int64_t(int_t):
    """Creates a signed 64-bit attribute"""
    def __init__(self, i=0):
        super().__init__(64, i)
        
class rand_int_t(int_t):
    """Creates a random signed arbitrary-width attribute"""
    
    def __init__(self, w=32, i=0):
        super().__init__(w, i)
        self._int_field_info.is_rand = True

class rand_int8_t(rand_int_t):
    """Creates a random signed 8-bit attribute"""
    def __init__(self, i=0):
        super().__init__(8, i)
        
class rand_int16_t(rand_int_t):
    """Creates a random signed 16-bit attribute"""
    def __init__(self, i=0):
        super().__init__(16, i)
        
class rand_int32_t(rand_int_t):
    """Creates a random signed 32-bit attribute"""
    def __init__(self, i=0):
        super().__init__(32, i)
        
class rand_int64_t(rand_int_t):
    """Creates a random signed 64-bit attribute"""
    def __init__(self, i=0):
        super().__init__(64, i)        
        
class list_t(object):
    
    def __init__(self, t):
        self.t = t
        self._int_field_info = field_info()
    
    def build_field_model(self, name):
        pass
    
    def size(self):
        print("size")
        if get_expr_mode():
            # TODO: return a size expression of the model
            pass
        else:
            return len(self.arr)

    def __iter__(self):
        class list_it(object):
            def __init__(self, l):
                self.model = l._int_field_info.model
                self.idx = 0
                
            def __next__(self):
                if self.idx >= len(self.model.field_l):
                    raise StopIteration()
                else:
                    v = self.model.field_l[self.idx].get_val()
                    self.idx += 1
                    return int(v)
        return list_it(self)
    
    def __getitem__(self, k):
        print("getitem: " + str(k))
        # TODO: what about arrays of composite objects
        model = self._int_field_info.model
        # How do we wrap this up?
        return int(model.field_l[k].get_val())
    
    def __setitem__(self, k, v):
        self.arr[k] = v
        
    def clear(self):
        # TODO: changing size should trigger behavior
        self.arr.clear()

    def append(self, v):
        # TODO: changing size should trigger behavior
        self.arr.append(v)
        
    def to_expr(self):
        return expr(ExprFieldRefModel(self._int_field_info.model))
    
class rand_list_t(list_t):
    """List of random elements with a non-random size"""
    
    def __init__(self, t, sz=0):
        super().__init__(t)
        self._init_sz = sz
        self._int_field_info.is_rand = True
        
    def get_model(self):
        if self._int_field_info.model is None:
            if isinstance(self.t, type_base):
                # Scalar type
                self._int_field_info.model = FieldScalarArrayModel(
                    "<unknown>",
                    self.t.width,
                    self.t.is_signed,
                    self._int_field_info.is_rand,
                    False)
                
                if self._init_sz > 0:
                    for i in range(self._init_sz):
                        field = self._int_field_info.model.add_field()
                        field.name = self._int_field_info.model.name + "[" + str(i) + "]"
            else:
                raise Exception("Composite-type arrays not yet supported")
            
        return self._int_field_info.model

    def build_field_model(self, name):
        # Lists are a bit special, since we need to be
        # able to fill 
        model = self.get_model()
        model.name = name
        self._int_field_info.name = name
        
        for i,f in enumerate(model.field_l):
            f.name = model.name + "[" + str(i) + "]"
        
        super().build_field_model(name)
        return model

class randsz_list_t(list_t):
    """List of random elements with a non-random size"""
    
    def __init__(self, t):
        super().__init__(t)
        self._int_field_info.is_rand = True
        
    def get_model(self):
        if self._int_field_info.model is None:
            if isinstance(self.t, type_base):
                # Scalar type
                self._int_field_info.model = FieldScalarArrayModel(
                    "<unknown>",
                    self.t.width,
                    self.t.is_signed,
                    self._int_field_info.is_rand,
                    True)
            else:
                raise Exception("Composite-type arrays not yet supported")
            
        return self._int_field_info.model

    def build_field_model(self, name):
        # Lists are a bit special, since we need to be
        # able to fill 
        model = self.get_model()
        model.name = name
        self._int_field_info.name = name
        
        for i,f in enumerate(model.field_l):
            f.name = model.name + "[" + str(i) + "]"
        
        super().build_field_model(name)
        return model
    
    def size(self):
        if get_expr_mode():
            return expr(ExprFieldRefModel(self._int_field_info.model.size))
        else:
            return int(self._int_field_info.model.size.get_val())
        
    def __iter__(self):
        class list_it(object):
            def __init__(self, l):
                self.model = l._int_field_info.model
                self.idx = 0
                
            def __next__(self):
                if self.idx >= int(self.model.size.get_val()):
                    raise StopIteration()
                else:
                    v = self.model.field_l[self.idx].get_val()
                    self.idx += 1
                    return int(v)
        return list_it(self)
    
    def __getitem__(self, k):
        # TODO: what about arrays of composite objects
        model = self._int_field_info.model
        # How do we wrap this up?
        return int(model.field_l[k].get_val())
    

