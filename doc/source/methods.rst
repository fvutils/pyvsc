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
