#################
Py-VSC Data Types
#################

Generating good random data requires characterizing the data to be randomized. 
Py-VSC provides specific data types to characterize the size and signed-ness
of fields to be used in constraints.

First, a quick example

.. code-block:: python3
    
    class my_s(vsc.RandObj):
         
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
            self.b in vsc.rangelist([self.c,self.d])

The example above shows using the ``rand_bit_t`` type to specify class attributes
that are random, unsigned (bit), and 8-bits wide.

In much the same way that C/C++ and SystemVerilog provide more than one way to 
capture types that are equivalent, Py-VSC provides several ways of capturing the
same type information. 

            