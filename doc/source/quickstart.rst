################
Quickstart Guide
################

Installing PyVSC
================


Installation via PyPi
---------------------

.. code-block:: bash

   pip install pyvsc

This installs the constraint solvers that publish a wheel for your platform:
Boolector on Linux and macOS, and dv-solve on Linux x86_64. Windows has no
Boolector wheel, so there PyVSC runs on dv-solve alone and selects it
automatically; it installs from PyPI once dv-solve publishes a Windows wheel,
and builds from source (``pip install`` of a dv-solve checkout) until then. See
:doc:`solver_backends`.

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

