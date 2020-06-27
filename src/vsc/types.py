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

from vsc.impl.ctor import push_expr, pop_expr, in_constraint_scope,\
    is_foreach_arr, expr_l
from vsc.impl.enum_info import EnumInfo
from vsc.impl.expr_mode import get_expr_mode, expr_mode
from vsc.model.bin_expr_type import BinExprType
from vsc.model.enum_field_model import EnumFieldModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_in_model import ExprInModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.expr_partselect_model import ExprPartselectModel
from vsc.model.expr_range_model import ExprRangeModel
from vsc.model.expr_rangelist_model import ExprRangelistModel
from vsc.model.field_scalar_model import FieldScalarModel
from vsc.model.value_scalar import ValueScalar
from vsc.model.field_array_model import FieldArrayModel
from lib2to3.btm_utils import TYPE_ALTERNATIVES
from vsc.model.expr_indexed_field_ref_model import ExprIndexedFieldRefModel
from vsc.model.field_const_array_model import FieldConstArrayModel
from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel
from vsc.model.expr_array_sum_model import ExprArraySumModel


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
        from .visitors.model_pretty_printer import ModelPrettyPrinter
        to_expr(rhs)

        rhs_e = pop_expr()
        lhs_e = pop_expr()
       
#        print("bin_expr: lhs=" + 
#              ModelPrettyPrinter.print(lhs_e) + " rhs=" +
#              ModelPrettyPrinter.print(rhs_e) + " len=" + 
#              str(len(expr_l)))
#        for e in expr_l:
#            print("    Expr: " + ModelPrettyPrinter.print(e))
        
        
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
    
class rng(object):
    
    def __init__(self, low, high):
        self.low = low
        self.high = high
        
class rangelist(object):
    
    def __init__(self, *args):
        if len(args) == 0:
            raise Exception("Empty rangelist specified")

        self.range_l = ExprRangelistModel()
        for i in range(-1,-(len(args)+1), -1):
            a = args[i]
            if isinstance(a, tuple):
                # This needs to be a two-element array
                if len(a) != 2:
                    raise Exception("Range specified with " + str(len(a)) + " elements is invalid. Two elements required")
                to_expr(a[0])
                to_expr(a[1])
                e1 = pop_expr()
                e0 = pop_expr()
                self.range_l.add_range(ExprRangeModel(e0, e1))
            elif isinstance(a, rng):
                to_expr(a.low)
                to_expr(a.high)
                e1 = pop_expr()
                e0 = pop_expr()
                self.range_l.add_range(ExprRangeModel(e0, e1))
            elif isinstance(a, list):
                list_f = FieldConstArrayModel("<<anonymous>>", a)
                self.range_l.add_range(ExprFieldRefModel(list_f))
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
    def __init__(self, is_composite=False):
        self.id = -1
        self.parent = None
        self.root_e = None
        self.is_composite = is_composite
        
        self.name = None
        self.is_rand = False
        self.model = None
        # Specifies whether an ExprIndexedFieldRef should be used
        self.indexed_ref = False
        
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
        if self._int_field_info.id != -1:
            # Need something like an indirect reference
            # - root reference
            # - leaf reference
            id_l = []
            fi = self._int_field_info
            
            while fi.parent is not None:
                id_l.insert(0, fi.id)
                fi = fi.parent

            return expr(ExprIndexedFieldRefModel(fi.root_e, id_l))
        else:
            return expr(ExprFieldRefModel(self._int_field_info.model))
    
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

#        push_expr(ExprFieldRefModel(self._int_field_info.model))
        # Push a reference to this field
        self.to_expr()

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
    
    def __init__(self, t, sz=0, is_rand=False, is_randsz=False):
        self.t = t
        self._int_field_info = field_info()
        self.is_scalar = isinstance(t, type_base)
        self._int_field_info.is_rand = is_rand
        self.is_rand_sz = is_randsz
        self.init_sz = sz
        if not self.is_scalar:
            if not hasattr(t, "_int_field_info"):
                raise Exception("list_t type " + str(t) + " (type " + str(type(t)) + ") is not a VSC randobj type")
            
            # Fill out field index and parent relationships
            # to support indexed field access
            # TODO: look out for recursive relationships...
            with expr_mode():
                self._id_fields(t, None)
            
        # Non-scalar arrays require a backing array
        self.backing_arr = []
        
    def _id_fields(self, it, parent):
        """Apply an ID to all fields, so they can be referenced in foreach constraints"""
        it._int_field_info.parent = parent

        fid = 0        
        for fn in dir(it):
            fo = getattr(it, fn)
            if hasattr(fo, "_int_field_info"):
                fi = fo._int_field_info
                fi.id = fid
                fi.parent = it._int_field_info
                fid += 1
                
                if fi.is_composite:
                    self._id_fields(fo, fi)
        
    def get_model(self):
        if self._int_field_info.model is None:
            self._int_field_info.model = FieldArrayModel(
                "<unknown>",
                self.is_scalar,
                self.t.width if self.is_scalar else -1,
                self.t.is_signed if self.is_scalar else -1,
                self._int_field_info.is_rand,
                self.is_rand_sz)
            
            if self.init_sz > 0:
                for i in range(self.init_sz):
                    if self.is_scalar:
                        self.append(0)
                    else:
                        self.append(type(self.t)())
                
            
        return self._int_field_info.model

    def build_field_model(self, name):
        model = self.get_model()
        model.name = name
        self._int_field_info.name = name
        
        return model

    @property    
    def size(self):
        model = self.get_model()
        if get_expr_mode():
            return expr(ExprFieldRefModel(model.size))
        else:
            return int(model.size.get_val())
        
    @property
    def sum(self):
        if self.is_scalar:
            if get_expr_mode():
                raise Exception("Constraints on sum not supported")
                return expr(ExprArraySumModel(self.get_model()))
            else:
                ret = 0
                for f in self.get_model().field_l:
                    v = int(f.get_val())
                    print("v: " + str(v))
                    ret += int(f.get_val())
                return ret
        else:
            raise Exception("Composite arrays do not have a sum")
            
        
    def __len__(self):
        if get_expr_mode():
            raise Exception("len cannot be used in constraints")
        else:
            return self.size
        
    def append(self, v):
        model = self.get_model()
        if self.is_scalar:
            # Working with a scalar
            f = model.add_field()
            f.set_val(v)
        else:
            if not issubclass(type(v), type(self.t)):
                raise Exception("Attempting to append illegal element to object array")
            self.backing_arr.append(v)
            model.append(v.get_model())
            # Propagate randomization information
            v.get_model().is_declared_rand = self.get_model().is_declared_rand
        
    def clear(self):
        self.get_model().clear()

    def __contains__(self, lhs):
        to_expr(lhs)
        return expr(ExprInModel(
            pop_expr(), 
            ExprRangelistModel(
                [ExprFieldRefModel(self.get_model())])))

    def __iter__(self):
        class list_scalar_it(object):
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
        class list_object_it(object):
            def __init__(self, l):
                self.l = l
                self.model = l._int_field_info.model
                self.idx = 0
                
            def __next__(self):
                if self.idx >= int(self.model.size.get_val()):
                    raise StopIteration()
                else:
                    v = self.l.backing_arr[self.idx]
                    self.idx += 1
                    return v
                
        if self.is_scalar:
            return list_scalar_it(self)
        else:
            return list_object_it(self)
    
    def __getitem__(self, k):
        model = self._int_field_info.model
        if get_expr_mode():
            # TODO: must determine whether we're within a foreach or just on our own
            if is_foreach_arr(self):
                to_expr(k)
                idx_e = pop_expr()
                
                return expr(ExprArraySubscriptModel(
                    ExprFieldRefModel(self.get_model()),
                    idx_e))
            else:
                to_expr(k)
                idx_e = pop_expr()
                return expr(ExprArraySubscriptModel(
                    ExprFieldRefModel(self.get_model()),
                    idx_e))
        else:
            if self.is_scalar:
                return int(model.field_l[k].get_val())
            else:
                return self.backing_arr[k]
            
    def __setitem__(self, k, v):
        if self.is_scalar:
            self.get_model().field_l[k].set_val(v)
        else:
            self.backing_arr[k] = v

    def to_expr(self):
        return expr(ExprFieldRefModel(self.get_model()))

    
class rand_list_t(list_t):
    """List of random elements with a non-random size"""
    
    def __init__(self, t, sz=0):
        super().__init__(t, sz, is_rand=True)
        
class randsz_list_t(list_t):
    """List of random elements with a non-random size"""
    
    def __init__(self, t):
        super().__init__(t, is_rand=True, is_randsz=True)
        

