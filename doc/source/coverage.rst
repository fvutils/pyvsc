##############
PyVSC Coverage
##############

Covergroups
===========

With PyVSC, a covergroup is declared as a Python class that is decorated
with the `covergroup` decorator.

.. code-block:: python3

        @vsc.covergroup        
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(
                    a=bit_t(4)
                    )
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : vsc.bin(1, 2, 4),
                    "b" : vsc.bin(8, [12,15])
                    })
                    
       my_cg_1 = my_covergroup()
       my_cg_2 = my_covergroup()

Data to be sampled for coverage can be passed to the covergroup as
parameters of the `sample` method when the covergroup is sampled, 
or may be specified as a reference parameter when the covergroup 
is instanced.

Coverage goals, coverage options, and sampling details are specified within
the `__init__` method.

Covergroup instances are created by creating an instance of a `covergroup`-decorated
class. 


Specifying Covergroup Options
-----------------------------

PyVSC covergroups contain an `options` attribute and a `type_options` attribute
with which to configure covergroup options. Options may only be changed within
the `__init__` method. 

.. note:: `options` and `type_options` attributes are provided, but the values are currently ignored

.. table:: Instance-Specific Coverage Options

+---------------------+-------------+--------------------------------------------------------------+
| Option name         | Default     | Description                                                  |
+=====================+=============+==============================================================+
| name=*string*       | Unique name | Specifies a name fo the covergroup instance. If unspecified, |
|                     |             | a unique name will be generated based on the type name.      |
+---------------------+-------------+--------------------------------------------------------------+
| weight=number       | 1           | Specifies the weight of this covergroup instances relative   |
|                     |             | to other instances.                                          |
+---------------------+-------------+--------------------------------------------------------------+
| goal=number         | 100         | Specifies the target goal for this covergroup instance       |
+---------------------+-------------+--------------------------------------------------------------+
| comment=*string*    | ""          | Specifes a comment for this covergroup                       |
+---------------------+-------------+--------------------------------------------------------------+
| at_least=number     | 1           | Minimum number of hits for each coverage bin                 |
+---------------------+-------------+--------------------------------------------------------------+
| auto_bin_max=number | 64          | Maximum number of automatically-created bins when bins are   |
|                     |             | not explicitly specified                                     |
+---------------------+-------------+--------------------------------------------------------------+
| per_instance=bool   | False       | When true, instance-specific coverage information must be    |
|                     |             | saved for each covergroup instance                           |
+---------------------+-------------+--------------------------------------------------------------+
| get_inst_coverage   | False       | Only applies when the *merge_instances* type option is set.  |
|                     |             | Enables tracking of per-instance coverage with the           |
|                     |             | *get_inst_coverage* method. When False, *get_coverage*       |
|                     |             | and *get_inst_coverage* return the same value.               |
+---------------------+-------------+--------------------------------------------------------------+

Options can be configured in two ways. Options maybe configured within the `__init__` method. 
They can also be configured after construction, and before the covergroup is sampled
for the first time, by referencing the options fields directly.

.. code-block:: python3

       @covergroup        
        class my_covergroup(object):
            
            def __init__(self, weight=1):
                self.with_sample(
                    a=bit_t(4)
                    )
                self.options.weight = weight
                self.cp1 = coverpoint(self.a, bins={
                    "a" : bin(1, 2, 4),
                    "b" : bin(8, [12,15])
                    })
                    
        cg1 = my_covergroup(10)
        cg2 = my_covergroup(20)

The example above sets the weight of the covergroup to the specified weight passed to `__init__`

.. code-block:: python3

       @vsc.covergroup        
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(
                    a=bit_t(4)
                    )
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : bin(1, 2, 4),
                    "b" : bin(8, [12,15])
                    })
                    
        cg1 = my_covergroup()
        cg1.options.weight=10
        cg2 = my_covergroup()
        cg2.options.weight=20

The example above configures the *weight* option by setting it post-cconstruction.


Coverpoints
===========

A coverpoint is declared using the `coverpoint` method. The name of the
coverpoint will be the same as the class attribute to which it is 
assigned. 

The first argument to a coverpoint is its target expression. This can be
an expression involving PyVSC-typed variables, or it can be a simple
reference to a callable field that returns a value.


Specifying Bins
---------------

Bins are specified as a Python `dict`, and passed via the `bins` keyword
argument to the coverpoint method. Both individual bins and arrays of 
bins can be specified.

Individual Bins
^^^^^^^^^^^^^^^

Individual bins are specified with the `bin` method. The `bin` method
accepts a list of individual values and value ranges that the bin contains.

.. code-block:: python3

       @vsc.covergroup        
        class my_covergroup(object):
            
            def __init__(self, a : callable):
            
                self.cp1 = vsc.coverpoint(a, bins={
                    "a" : vsc.bin(1, 2, 4),
                    "b" : vsc.bin(8, [12,15])
                    })

In the example above, the `a` bin contains the values 1, 2, 4. The `b` bin
contains the value 8 and the value range 12..15.

Bin Arrays
^^^^^^^^^^
Bin arrays partition a list of values and ranges into a specified number 
of bins. Bin arrays are specified using the `bin_array` method. The first
parameter to this method specifies how values are to be partitioned. This
parameter can be specified either as a number, or a single value in a list.
The list format is similar to SystemVerilog syntax.

.. code-block:: python3

       @vsc.covergroup        
        class my_covergroup(object):
            
            def __init__(self, a : callable):
            
                self.cp1 = vsc.coverpoint(a, bins={
                    "a" : vsc.bin_array([], 1, 2, 4),
                    "b" : vsc.bin_array([4], [8,16])
                    })

In the example above, bin `a` will consist of three individual value bins, 
with a bin for value 1, 2, and 4 respectively. Bin `b` will consist of
four bins, each covering two values of the range 8..16.

Auto-Bins
^^^^^^^^^
Auto-binning can be used in many cases to cause bins to be created for 
all values of an enumerated type, or to cause the legal value range to be
partitioned evenly based on the `auto_bin_max` option. 
When auto-binning is used and the type of the coverpoint isn't apparent, 
the `cp_t` parameter must be used to specify the type of the value being
sampled. 

.. code-block:: python3

       @vsc.covergroup        
        class my_covergroup(object):
            
            def __init__(self, a : callable):
            
                self.cp1 = vsc.coverpoint(a, cp_t=vsc.uint8_t())
                
In the example above, the type of the coverpoint is not apparent because
a callable is providing the target value. Consequently, the cp_t 
parameter is used to specify that the value being sampled is an 8-bit
unsigned integer.

Wildcard Bins (Single)
^^^^^^^^^^^^^^^^^^^^^^
A wildcard specification may be used to specify the values within 
single bins. The checked value may either be specified as a string
that contains wildcard characters ('x', '?') or may be specified
as a tuple of (value, mask).

When using the string form of specifying a wildcard bin, the 
specification string must start with "0x" (hexadecimal), 
"0o" (octal), or "0b" (binary).

Here is an example showing specification of a wildcard bin that 
matches any value 0x80..0x8F:

.. code-block:: python3

        @vsc.covergroup
        class cg(object):
            
            def __init__(self):
                self.with_sample(
                    dict(a=vsc.bit_t(8)))
                
                self.cp_a = vsc.coverpoint(self.a, bins=dict(
                    a=vsc.wildcard_bin("0x8x")))

Here is the same coverpoint specification using the value/mask
form:

.. code-block:: python3

        @vsc.covergroup
        class cg(object):
            
            def __init__(self):
                self.with_sample(
                    dict(a=vsc.bit_t(8)))
                
                self.cp_a = vsc.coverpoint(self.a, bins=dict(
                    a=vsc.wildcard_bin((0x80,0xF0))
                    ))

Wildcard Bins (Array)
^^^^^^^^^^^^^^^^^^^^^                    
A wildcard specification may also be used to specify arrays of bins.
In this case, the wildcard characters specify a location where all
possibilities must be expanded.

The example below creates 16 bins for the values 0x80..0x8F:

.. code-block:: python3

        @vsc.covergroup
        class cg(object):
            
            def __init__(self):
                self.with_sample(
                    dict(a=vsc.bit_t(8)))
                
                self.cp_a = vsc.coverpoint(self.a, bins=dict(
                    a=vsc.wildcard_bin_array([], "0x8x")
                    ))

Coverpoint Crosses
------------------

Coverpoint crosses are specified using the `cross` method. The first
parameter to the `cross` method is a list of the coverpoints that 
compose the coverpoint cross. 

.. code-block:: python3

        @vsc.covergroup
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(
                    a=bit_t(4),
                    b=bit_t(4)
                )
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : vsc.bin_array([], [1,15])
                    })
                self.cp2 = vsc.coverpoint(self.b, bins={
                    "a" : vsc.bin_array([], [1,15])
                    })
                
                self.cp1X2 = vsc.cross([self.cp1, self.cp2])

Specifying Coverpoint Sampling Conditions
-----------------------------------------
A sampling condition can be specified on both coverpoints and coverpoint
crosses using the `iff` keyword parameter to the `coverpoint` and `cross`
methods. 

.. code-block:: python3

       @vsc.covergroup        
        class my_covergroup(object):
            
            def __init__(self, a : callable, b : callable):
            
                self.cp1 = vsc.coverpoint(a, iff=b, bins={
                    "a" : vsc.bin_array([], 1, 2, 4),
                    "b" : vsc.bin_array([4], [8,16])
                    })


Coverpoint Options
------------------
Both type options and instance options can specified on both coverpoints
and coverpoint crosses. Only the following options are currently 
respected:

+---------------------+-------------+--------------------------------------------------------------+
| Option name         | Default     | Description                                                  |
+=====================+=============+==============================================================+
| weight=number       | 1           | Specifies the weight of this covergroup instances relative   |
|                     |             | to other instances.                                          |
+---------------------+-------------+--------------------------------------------------------------+
| goal=number         | 100         | Specifies the target goal for this covergroup instance       |
+---------------------+-------------+--------------------------------------------------------------+
| at_least=number     | 1           | Minimum number of hits for each coverage bin                 |
+---------------------+-------------+--------------------------------------------------------------+
| auto_bin_max=number | 64          | Maximum number of automatically-created bins when bins are   |
|                     |             | not explicitly specified                                     |
+---------------------+-------------+--------------------------------------------------------------+

Options are specified via a ``dict`` attached to the coverpoint 
during construction. The example below shows overriding the 
covergroup-level ``at_least`` option for one coverpoint.

.. code-block:: python3

        @vsc.covergroup
        class cg(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t(),
                    b=vsc.uint8_t()))
                
                self.options.at_least = 2
                
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : vsc.bin_array([], 1, 2, 4, 8),
                    }, options=dict(at_least=1))
                self.cp2 = vsc.coverpoint(self.b, bins={
                    "b" : vsc.bin_array([], 1, 2, 4, 8)
                    })

Providing Coverage Data to Sample
=================================
PyVSC supports several methods for providing data for a covergroup 
instance to sample.
- Data in a `randobj`-decorated class object can be provided by
reference to the covergroup `__init__` method.
- Scalar data can be specified to the `__init__` method using
lambda expressions to obtain the data from the instantiating context
- Data can be provided via the `sample` methods, using a user-specified
sample-method signature.
  
  
Declaring a Custom Sample Method
--------------------------------

Use of a custom `sample` method that accepts parameters is specified 
by calling the `with_sample` method and passing either a `dict` of 
parameter-name/parameter-type pairs or a list of keyword arguments.
The `with_sample` method declares class members with the same name
and type as the key/value pairs in the dict passed to the 
`with_sample` method.
The `with_sample` method should be called early in the ``__init__`` 
method body to ensure that the sample parameters are declared early 
and present when referenced in coverpoints.

.. code-block:: python3

       @vsc.covergroup        
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(dict(
                    a=bit_t(4)
                    ))
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : vsc.bin(1, 2, 4),
                    "b" : vsc.bin(8, [12,15])
                    })

The example above shows specifying the `sample` method parameter list 
using a `dict`. 

.. code-block:: python3

       @vsc.covergroup        
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(
                    a=bit_t(4)
                    )
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : vsc.bin(1, 2, 4),
                    "b" : vsc.bin(8, [12,15])
                    })


The example above shows specifying the `sample` method parameter list 
using individual keyword arguments.

.. code-block:: python3

        @vsc.covergroup        
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(
                    a=bit_t(4)
                    )
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : vsc.bin(1, 2, 4),
                    "b" : vsc.bin(8, [12,15])
                    })

        cg = my_covergroup()
        cg.sample(1)
        cg.sample(12)
            

In both cases, data is passed as parameters to the `sample` method, 
as shown in the example above.


Specifying Sampling Data at Instantiation
-----------------------------------------
PyVSC supports specifying coverage-sampling data when the covergroup
is instanced, as well as specifying it each time the sample method is
called. In this case, no parameters are passed to the `sample` method.

This mode of specifying coverage-sampling data requires that a `lambda`
is used to connect the calling context to the data used for coverage 
sampling. 

.. code-block:: python3

       @covergroup
        class my_covergroup(object):
            
            def __init__(self, a, b): # Need to use lambda for non-reference values
                super().__init__()
                
                self.cp1 = coverpoint(a, 
                    bins=dict(
                        a = bin_array([], [1,15])
                    ))
                
                self.cp2 = coverpoint(b, bins=dict(
                    b = bin_array([], [1,15])
                    ))
                
                
        a = 0;
        b = 0;
        
        cg = my_covergroup(lambda:a, lambda:b)

        a=1
        b=1
        cg.sample() # Hit the first bin of cp1 and cp2

In the example above, calling the `sample` method will sample the current value
of `a` and `b` in the context and sample the coverpoints with those values.


Coverage Reports
================

PyVSC provides three methods for obtaining a coverage report. 
- `get_coverage_report_model` -- Returns a coverage-report object with information about each type and instance of coverage
- `get_coverage_report` -- Returns a string with a textual coverage report
- `report_coverage` -- Prints a coverage report to a stream (defaults to stdout)







