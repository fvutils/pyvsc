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

Ignore and Illegal Bins
^^^^^^^^^^^^^^^^^^^^^^^
`Ignore` and `illegal` bins may be specified on coverpoints in
addition to the other bins described above. An ignore or illegal
bin trims values from other bins if it intersects values within
those bins. Please note that, as in SystemVerilog, bins are 
partitioned *after* ignore and illegal bin values are removed 
from regular bins. 

.. code-block:: python3

     @vsc.covergroup
        class val_cg(object):
            def __init__(self):
                self.with_sample(dict(
                    a=vsc.uint8_t()
                    ))
                self.cp_val = vsc.coverpoint(self.a, bins=dict(
                                    rng_1=vsc.bin_array([4], [1,3], [4,6], [7,9], [10,12])
                                ),
                                ignore_bins=dict(
                                    invalid_value=vsc.bin(4)
                                ))

In the example above, the user specifies an array of four 
auto-partitioned bins and an ignored value of `4`. In the 
absence of ignore bins, the 12 values to be paritionted 
would be divided into bins of three (1..3, 4..6, 7..9, 10..12).
Because bins are partitioned after excluded bins have been
applied, the bins in the example above are:
- 1..2
- 3,5
- 6,7
- 8..12
  
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

Coverpoint Cross Ignore Bins
............................

Coverpoint cross-bins to ignore may be specified as follows.

.. code-block:: python3
    def filter(a, b):
        v_set = (1, 2, 4, 8)
        for i,v in enumerate(v_set):
            b_set = v_set[i+1:]
            if len(b_set) and a.intersect(v) and b.intersect(b_set):
                print("Intersect: a: %s ; b: %s" % (str(a.range), str(b.range)))
                return True
        return False


    @vsc.covergroup
    class cg_t(object):
        def __init__(self):
            self.with_sample(dict(
                a=vsc.int8_t(),
                b=vsc.int8_t()))
            self.cp_a = vsc.coverpoint(self.a, 
                bins=dict(rng=vsc.bin_array([], 1, 2, 4, 8)))
            self.cp_b = vsc.coverpoint(self.b, 
                bins=dict(rng=vsc.bin_array([], 1, 2, 4, 8)))
            self.cr = vsc.cross([self.cp_a, self.cp_b], ignore_bins=dict(b1=filter))

The `ignore_bins` argument must be a dictionary of bin-name and filter-method.
The filter function is invoked with a bin specification for each coverpoint
in the cross-point. The function returns `True` if the specified bin 
combination should be ignored and `False`` otherwise. In this case,
bins where (b>a) are ignored.


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

Coverage API
============
PyVSC covergroup classes implement methods for querying achieved coverage.

- `get_coverage` - Reports coverage achieved by all covergroup instances (0..100)
- `get_inst_coverage` - Reports coverage by this instance (0..100)

.. code-block:: python3

        @vsc.covergroup        
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(
                    a=vsc.bit_t(4)
                    )
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : vsc.bin_array([], [1, 2, 4, 8])
                    })

        cg1 = my_covergroup()
        cg2 = my_covergroup()
        
        cg1.sample(1)
        print("Type=%f cg1=%f cg2=%f" % (
          cg1.get_coverage(),
          cg1.get_inst_coverage(),
          cg2.get_inst_coverage()))
          
        cg2.sample(2)
        print("Type=%f cg1=%f cg2=%f" % (
          cg1.get_coverage(),
          cg1.get_inst_coverage(),
          cg2.get_inst_coverage()))

Running this example produces:

.. code-block::

  Type=25.000000 cg1=25.000000 cg2=0.000000
  Type=50.000000 cg1=25.000000 cg2=25.000000

Sampling the first covergroup instance results in its instance coverage 
being increased to 25% (1/4 bins have been hit) and the combined type
coverage incrasing to 25%. Sampling the second covergroup instance raises
its instance coverage to 25% as well, while increasing the total type
coverage achieved to 50%.

Coverage Reports
================

PyVSC provides three methods for obtaining a coverage report. 

.. automodule:: vsc
  :members: get_coverage_report

.. automodule:: vsc
  :members: get_coverage_report_model

.. automodule:: vsc
  :members: report_coverage
 
Let's using a derivative of the example show above to see the differences 
between a coverage report with and without details.

.. code-block:: python3

        @vsc.covergroup        
        class my_covergroup(object):
            
            def __init__(self):
                self.with_sample(
                    a=vsc.bit_t(4)
                    )
                self.cp1 = vsc.coverpoint(self.a, bins={
                    "a" : vsc.bin_array([], 1, 2, 4, 8)
                    })

        cg1 = my_covergroup()
        cg2 = my_covergroup()
       
        cg1.sample(1)
        cg2.sample(2)
        
        print("==== Without Details ===")
        vsc.report_coverage()
        print()
        print("==== With Details ===")
        vsc.report_coverage(details=True)

The output from this code is shown below:

.. code-block::

    TYPE my_covergroup : 50.000000%
      CVP cp1 : 50.000000%
      INST my_covergroup : 25.000000%
          CVP cp1 : 25.000000%
      INST my_covergroup_1 : 25.000000%
          CVP cp1 : 25.000000%

    ==== With Details ===
    TYPE my_covergroup : 50.000000%
      CVP cp1 : 50.000000%
      Bins:
          a[0] : 1
          a[1] : 1
          a[2] : 0
          a[3] : 0
      INST my_covergroup : 25.000000%
          CVP cp1 : 25.000000%
          Bins:
              a[0] : 1
              a[1] : 0
              a[2] : 0
              a[3] : 0
      INST my_covergroup_1 : 25.000000%
          CVP cp1 : 25.000000%
          Bins:
              a[0] : 0
              a[1] : 1
              a[2] : 0
              a[3] : 0
 

The coverage report without details shows the coverage achieved for the
covergroup and coverpoints without showing which bins were hit or how
many times. The coverage report with details shows hit counts for each
bin in addition to the coverage percentage achieved for the covergroups
and coverpoints.
 
Saving Coverage Data
====================

PyVSC uses the `PyUCIS <https://github.com/fvutils/pyucis>`_ library to export
coverage data using the API or XML interchange format defined by the
`Accellera UCIS <https://accellera.org/downloads/standards/ucis>`_ standard.

Using the PyUCIS library, PyVSC can write coverage data to an XML-format
coverage interchange file. Or, can write coverage data directly to a
coverage database using a shared library that implements the UCIS C API.

PyVSC provides the `write_coverage_db` method for saving coverage data.

.. automodule:: vsc
  :members: write_coverage_db

Saving to XML
-------------

By default, the `write_coverage_db` method saves coverage data to an
XML file formatted according to the UCIS interchange-format schema.

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
       my_cg_1.sample(1)
       my_cg_1.sample(2)
       my_cg_1.sample(8)
       
       vsc.write_coverage_db('cov.xml')
       
Saving via a UCIS API Implementation
------------------------------------

When an implementation of the UCIS C API is available, PyVSC
can write coverage data using that API implementation. In this
case, the `fmt` parameter of the `write_coverage_db` method 
must be specified as `libucis`. The `libucis` parameter of 
the method must specify the name of the shared library that
implements the UCIS API.

In the example below, the tool-provided shared library that
implements the UCIS API is named `libucis.so`. 

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
       my_cg_1.sample(1)
       my_cg_1.sample(2)
       my_cg_1.sample(8)
       
       vsc.write_coverage_db('cov.db', fmt='libucis', libucis='libucis.so')

Calling `write_coverage_db` in this way causes the PyUCIS library
to load the specified shared library and call UCIS C API functions
to record the coverage data collected by the PyVSC library.

Using Coverage Data
===================

Coverage data saved from PyVSC can be used in several open-source and
closed-source commercial tool flows. The sections below describe 
flows that PyVSC data is known to have been used in.

.. note::

  The information below with respect to closed-source/commercial tool 
  flows represents data collected from users of those flows and tools. 
  You are well-advised to confirm the accuracy of the information 
  with the relevant vendor's documentation and/or Application Engineers.

Please report other tool flows that accept coverage data from PyVSC
via the project's `Issues <https://github.com/fvutils/pyvsc/issues>`_ or 
`Discussion <https://github.com/fvutils/pyvsc/discussions>`_ areas.

Viewing Coverage with PyUCIS-Viewer
-----------------------------------

`PyUCIS-Viewer <https://github.com/fvutils/pyucis-viewer>`_ is a very
simple graphical viewer for functional coverage data. It currently 
supports reading coverage data from UCIS XML-interchange-formatted
files.

Siemens Questa: Writing Coverage Data
-------------------------------------

Siemens Questa [#]_ is reported to provide a library that implements the 
UCIS C API. Using this library, coverage data can be written
directly to a Questa coverage database. See the information above about
writing coverage data to a UCIS API implementation for more information
on how to utilize this flow.

 
Synopsys VCS: Importing Coverage Data
-------------------------------------

Bringing coverage in UCIS XML-interchange format into the Synopsys VCS [#]_ 
metric analysis flow has been described using an import command. To follow
this flow, write coverage data out from PyVSC in UCIS XML-interchange format.

Use the following VCS import command to read the data from the XML coverage
file into a VCS coverage database:

.. code:: shell

  % covimport -readucis <cov.xml> -dbname <cov.vdb>



.. [#] Questa is a trademark of Siemens Industry Software Inc.
.. [#] VCS is a trademark of Synopsys Inc.



