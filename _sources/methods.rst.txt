#############
PyVSC Methods
#############

Randomization Methods
=====================

In addition to the `randomize` and `randomize_with` methods provided by the
randobj class, PyVSC provides global methods for randomizing variables.


.. code-block:: python3

        a = vsc.rand_uint8_t()
        b = vsc.rand_uint8_t()

        vsc.randomize(a, b)

The global randomize method randomizes the list of PyVSC variables, both
scalar and composite.


.. code-block:: python3

        a = vsc.rand_uint8_t()
        b = vsc.rand_uint8_t()

        for i in range(10): 
            with vsc.randomize_with(a, b):
                a < b

The global randomize_with method randomizes the list of PyVSC variables, 
both scalar and composite, subject to the inline constraints.

Managing Random Stability
=========================

Each PyVSC `rand_obj` instance maintains its own random state. The 
random state for each `rand_obj` can be established explicitly by
the user. If the random state has not been initialized at the time
of the first call to `randomize` on a object, the random state
will be automatically derived using the Python `random` package. 

PyVSC uses the `RandState` class to store and manipulate random state.
The `rand_obj` class provides functions for obtaining a copy of the
current random state, and for setting the current random state to 
that of a previously-obtained random state.

The example below shows using a RandState object to produce the 
same sequence of random number twice.

.. code-block:: python3

        @vsc.randobj
        class item_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
            
            @vsc.constraint
            def ab_c(self):
                self.a < self.b

        ci = item_c()
        
        v1 = []
        v2 = []

        print("Iteration 1")        
        rs1 = RandState.mkFromSeed(0)
        ci.set_randstate(rs1)
        for _ in range(10):
            ci.randomize()
            v1.append((ci.a,ci.b))

        print("Iteration 2") 
        ci.set_randstate(rs1)
        for _ in range(10):
            ci.randomize()
            v2.append((ci.a,ci.b))

The `RandSeed.mkFromSeed` method is the preferred way to 
create a random state object from user-specified values. The
mkFromSeed method accepts an integer seed and an optional 
string. The example below shows producing the same sequence
of random values based on two independently-created random
state objects.

.. code-block:: python3

        @vsc.randobj
        class item_c(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
            
            @vsc.constraint
            def ab_c(self):
                self.a < self.b

        ci = item_c()
        
        v1 = []
        v2 = []

        print("Iteration 1")        
        rs1 = RandState.mkFromSeed(10, "abc")
        ci.set_randstate(rs1)
        for _ in range(10):
            ci.randomize()
            v1.append((ci.a,ci.b))

        print("Iteration 2") 
        rs2 = RandState.mkFromSeed(10, "abc")
        ci.set_randstate(rs2)
        for _ in range(10):
            ci.randomize()
            v2.append((ci.a,ci.b))


Weighted-Random Selection Methods
=================================

It is often useful to perform a weighted-random selection in procedural 
code. SystemVerilog provides the `randcase` construct for this purpose.
PyVSC provides two methods for performing a weighted-random selection
from a set of candidates.

distselect
----------

The `distselect` method accepts a list of weights and returns the selected
index. 

.. code-block:: python3

        hist = [0]*4
        
        for i in range(100):
            idx = vsc.distselect([1, 1, 10, 10])
            hist[idx] += 1
            
        print("hist: " + str(hist))

In the example above, the index returned will vary 0..3.


randselect
----------
The `randselect` method accepts a list of weight/lambda tuples. It performs
a weighted selection and calls the selected lambda. In most cases, the lambda
will need to call a function to perform useful work.

.. code-block:: python3

        hist = [0]*4
        
        def task(idx):
            hist[idx] += 1

        for i in range(100):
            vsc.randselect([
                   (1, lambda: task(0)),
                   (1, lambda: task(1)),
                   (10, lambda: task(2)),
                   (10, lambda: task(3))])
        print("hist: " + str(hist))

In the example above, the lambda functions invoke the same Python method with
different arguments. Different methods could be called instead.


