#####
Debug
#####

There are several situations in which you may need to enable or 
configure debug with PyVSC. The most common is when a set of
constraints fails to solve, and diagnostics must be enabled 
to help understand the reason for the failure. PyVSC targets 
execution speed over verbosity, so default behavior is to
create no diagnostics when a solve failure occurs.

Enabling Solve-Fail Debug
=========================

PyVSC provides an optional argument to the `randomize` and
`randomize_with` method to enable solve-fail debug on a
per-call basis. 

.. code-block:: python3

        class my_e(IntEnum):
            A = auto()
            B = auto()
            C = auto()
            
        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.e = vsc.rand_enum_t(my_e)
                self.a = vsc.rand_uint8_t()
                
            @vsc.constraint
            def a_c(self):
                self.a == 1
                with vsc.if_then(self.a == 2):
                    self.e == my_e.A
                
        it = my_c()

        with it.randomize_with(solve_fail_debug=1):
            it.a == 2

In the example above, the class-level constraint set
forces a==1, while the user's inline constraints forces
a==2. The `randomize_with` call sets solve_fail_debug=1,
which triggers creation of diagnostic information when
a solve failure occurs.

In this case, the output is of the following form:

.. code-block::

  Problem Set: 2 constraints
    <unknown>:
      (a == 1);
    <unknown>:
      (a == 2);
      
Enabling solve-fail debug can also be enabled globally
by calling `vsc.vsc_solvefail_debug(1)` from Python code. 
The environment variable VSC_SOLVEFAIL_DEBUG can also 
be set to 1.

Capturing Source Information
============================
Note that no source information is available for the constraints. 
This is because querying source information in Python is quite 
time-consuming. 

Enabling the capture of source information for constraints can be
done in two ways: via the `randobj` decorator, and via an 
environment variable. 

.. code-block:: python3

        class my_e(IntEnum):
            A = auto()
            B = auto()
            C = auto()
            
        @vsc.randobj(srcinfo=True)
        class my_c(object):
            
            def __init__(self):
                self.e = vsc.rand_enum_t(my_e)
                self.a = vsc.rand_uint8_t()
                
            @vsc.constraint
            def a_c(self):
                self.a == 1
                with vsc.if_then(self.a == 2):
                    self.e == my_e.A
                
        it = my_c()

        with it.randomize_with(solve_fail_debug=1):
            it.a == 2


In the code-block above, the `srcinfo` parameter to the
`randobj` decorator causes source information to be 
collected for constraints in the class. The solve-fail
diagnostics will now be of the following form:

.. code-block::

  Problem Set: 2 constraints
    /project/fun/pyvsc/pyvsc-partsel-rand/ve/unit/test_solve_failure.py:30:
      (a == 1);
    /project/fun/pyvsc/pyvsc-partsel-rand/ve/unit/test_solve_failure.py:38:
      (a == 2);
    

Source-information capture may also be enabled globally
via an environment variable. Set VSC_CAPTURE_SRCINFO=1 to cause
all source information for all random classes to be captured.

