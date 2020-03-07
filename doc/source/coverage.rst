###############
Py-VSC Coverage
###############


Covergroups
===========

With Py-VSC, a covergroup is declared as a Python class that is decorated
with the `@covergroup` decorator.

.. code-block:: python3
       @covergroup        
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=bit_t(4)
                    ))
                self.cp1 = coverpoint(self.a, bins={
                    "a" : bin(1, 2, 4),
                    "b" : bin(8, [12,15])
                    })

Data to be sampled for coverage can be passed to the covergroup as
parameters of the `sample` method when the covergroup is sampled, 
or may be specified as a reference parameter when the covergroup 
is instanced.


Declaring a Sample Method
-------------------------

Use of the `sample` method is specified by calling the `with_sample`
method and passing a `dict` of paramter-name/parameter-type pairs.
The `with_sample` method declares class members with the same name
and type as the key/value pairs in the dict passed to the 
`with_sample` method.
The `with_sample` method should be called early in the __init__ 
method body to ensure that the sample parameters are declared early.

.. code-block:: python3
       @covergroup        
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=bit_t(4)
                    ))
                self.cp1 = coverpoint(self.a, bins={
                    "a" : bin(1, 2, 4),
                    "b" : bin(8, [12,15])
                    })



Specifying Covergroup Options
-----------------------------
Py-VSC supports the same set of options that a SystemVerilog covergroup
does. Type options are specified within the __init__ method via the
`type_options` attribute. Instance options are specified within the
__init__ method via the `options` attribute.

Creating a Covergroup Instance
------------------------------

Covergroup instances are created by instancing the 

Specifying Sampling Data at Instantiation
-----------------------------------------
Py-VSC supports specifying coverage-sampling data when the covergroup
is instanced, as well as specifying it each time the sample method is
called. In this case, no parameters are passed to the `sample` method.

This mode of specifying coverage-sampling data requires that a lambda 
is used to connect the calling context to the data used for coverage 
sampling. See the example below.

.. code-block:: python3
       @covergroup
        class my_covergroup(object):
            
            def __init__(self, a, b, c): # Need to use lambda for non-reference values
                super().__init__()
                
                self.cp1 = coverpoint(a, 
                    bins=dict(
                        a = bin_array([], [1,15])
                    ))
                
                self.cp2 = coverpoint(b, bins=dict(
                    b = bin_array([], [1,15])
                    ))
                
                
        a = 1;
        b = 2;
        
        cg = my_covergroup(lambda:a, lambda:b, lambda:c)

        cg.sample()

Passing a lambda as an __init__-method allows the covergroup to sample
the current value of the 




Coverpoints
===========

A coverpoint is declared using the `coverpoint` method. The name of the
coverpoint will be the same as the class attribute to which it is 
assigned. 

Declaring a Coverpoint
----------------------


Specifying Bins
---------------


Coverpoint Crosses
==================

Coverpoint crosses are specified using the `cross` method. The first
parameter to the `cross` method is a list of the coverpoints that 
compose the coverpoint cross. 

.. code-block:: python3
        @covergroup
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=bit_t(4),
                    b=bit_t(4)
                ))
                self.cp1 = coverpoint(self.a, bins={
                    "a" : bin_array([], [1,15])
                    })
                self.cp2 = coverpoint(self.b, bins={
                    "a" : bin_array([], [1,15])
                    })
                
                self.cp1X2 = cross([self.cp1, self.cp2])

Specifying Coverpoint Sampling Conditions
=========================================
A sampling condition can be specified on both coverpoints and coverpoint
crosses. 

Coverpoint Options
==================
Both type options and instance options can specified on both coverpoints
and coverpoint crosses.

