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


