################
PyVSC Data Types
################

Generating good random data requires characterizing the data to be randomized. 
PyVSC provides specific data types to characterize the size and signedness
of fields to be used in constraints.

First, a quick example

.. code-block:: python3

    @vsc.randobj    
    class my_s(object):
         
        def __init__(self):
            self.a = vsc.rand_bit_t(8)
            self.b = vsc.rand_bit_t(8)
            self.c = vsc.rand_bit_t(8)
            self.d = vsc.rand_bit_t(8)
             
        @vsc.constraint
        def ab_c(self):
             
            self.a in vsc.rangelist(1, 2, 4, 8)

            self.c != 0
            self.d != 0
             
            self.c < self.d
            self.b in vsc.rangelist(vsc.rng(self.c,self.d))

The example above shows using the `rand_bit_t` type to specify class attributes
that are random, unsigned (bit), and 8-bits wide.

In much the same way that C/C++ and SystemVerilog provide more than one way to 
capture types that are equivalent, PyVSC provides several ways of capturing the
same type information. 

Scalar Standard-Width Attributes
================================

PyVSC provides a set of standard-width data types, modeled after the types defined
in :file:`stdint.h`. Both random and non-random variants of these attribute classes are 
provided.

=====  ======  ===============  ==============
Width  Signed  Random           Non-Random
8      Y       `rand_int8_t`    `int8_t`
8      N       `rand_uint8_t`   `uint8_t`
16     Y       `rand_int16_t`   `int16_t`
16     N       `rand_uint16_t`  `uint16_t`
32     Y       `rand_int32_t`   `int32_t`
32     N       `rand_uint32_t`  `uint32_t`
64     Y       `rand_int64_t`   `int64_t`
64     N       `rand_uint64_t`  `uint64_t`
=====  ======  ===============  ==============

The constructor for the classes above accepts the initial value for the
class attribute. By default, the initial value will be 0.

.. code-block:: python3
    
    @vsc.randobj    
    class my_s(object):
         
        def __init__(self):
            self.a = vsc.rand_uint8_t()
            self.b = vsc.uint16_t(2)
            self.c = vsc.rand_int64_t()

In the example above, a random unsigned 8-bit field, a non-random unsigned 
16-bit field, and a random signed 64-bit field is created. 

Scalar Arbitrary-Width Attributes
=================================

PyVSC provides four classes for constructing arbitrary-width scalar class attributes.
The first parameter of the class constructor is the width. The second parameter
specifies the initial value for the attribute.

======  ==============  ==============
Signed  Random          Non-Random
Y       `rand_int_t`    `int_t`
N       `rand_bit_t`    `bit_t`
======  ==============  ==============

.. code-block:: python3
    
    @vsc.randobj    
    class my_s(object):
         
        def __init__(self):
            self.a = vsc.rand_int_t(27)
            self.b = vsc.rand_bit_t(12)

The example above creates a random signed 27-bit attribute and a 
random unsigned 12-bit attribute.


Enum-type Attributes
====================

PyVSC supports Python :class:`~enum.Enum` and :class:`~enum.IntEnum` enumerated types. Attributes
are declared using the `enum_t` and `rand_enum_t` classes.

.. code-block:: python3
    
    class my_e(Enum):
      A = auto()
      B = auto()
      
    @vsc.randobj    
    class my_s(object):
         
        def __init__(self):
            self.a = vsc.rand_enum_t(my_e)
            self.b = vsc.enum_t(my_e)

Class-type Attributes
=====================

Random and non-random class attributes can be created using classes
decorated with `randobj`. Non-random class attributes can optionally
be decorated with `attr`.

.. code-block:: python3
    
    @vsc.randobj    
    class my_sub_s(object):
        def __init__(self):
            self.a = vsc.rand_uint8_t()
            self.b = vsc.rand_uint8_t()
      
    @vsc.randobj    
    class my_s(object):
         
        def __init__(self):
            self.i1 = vsc.rand_attr(my_sub_s())
            self.i2 = vsc.attr(my_sub_s())
            

Accessing Attribute Values
==========================

The value of scalar attributes can be accessed in two ways. All PyVSC scalar attribute
types provide a `get_val()` and `set_val()` method. These methods can be called to
get or set the current value.

PyVSC also provides operator overloading for `randobj`-decorated classes that 
allows the value of class attributes to be accessed directly.


