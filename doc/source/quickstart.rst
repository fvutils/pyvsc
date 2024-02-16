################
Quickstart Guide
################

Installing PyVSC
================


Installation via PyPi
---------------------

.. code-block:: bash

   pip install pyvsc

Installation from Source
------------------------

.. code-block:: bash

   cd pyvsc
   pip install -e .


A Simple Example
========================

.. code-block:: python3

    import vsc

    a = vsc.rand_uint8_t()
    b = vsc.rand_uint8_t()

    for _ in range(10):
        with vsc.randomize_with(a, b):
            a < b
        print(a.get_val(), b.get_val())

