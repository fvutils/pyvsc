################
Quickstart Guide
################

Installing PyVSC
================


Installation via PyPi
---------------------

.. code-block:: bash

   pip install pyvsc

This installs two constraint solvers:

* **Boolector**, the solver PyVSC has always used. It is installed on Linux
  x86_64 and macOS, and it remains the default there.
* **dv-solve**, PyVSC's new native solver, installed on every platform
  (Linux x86_64 and aarch64, macOS x86_64 and arm64, Windows AMD64). It is
  the default on Windows and Linux aarch64, where Boolector has no wheel.

To try dv-solve where Boolector is the default, select it with an environment
variable or from Python:

.. code-block:: bash

   VSC_SOLVER=dv-solve python my_test.py

.. code-block:: python

   import vsc
   vsc.set_solver_backend("dv-solve")

See :doc:`solver_backends`.

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

