#####################
Solver Back-ends
#####################

PyVSC solves randomization constraints through a pluggable *solver back-end*.
The back-end is selected once per ``randomize()`` call and is responsible for
translating a group of related fields and constraints (a *RandSet*) into a
form its underlying engine understands, solving it, and writing the solved
values back into the fields.

.. note::
   During the dv-solve integration the default back-end is **Boolector**, the
   engine PyVSC has always used. Additional back-ends (``dv-solve``) are being
   introduced incrementally and are opt-in until conformance is demonstrated.

Selecting a back-end
====================

Two mechanisms select the back-end, in increasing precedence:

* **Environment variable** ``VSC_SOLVER`` -- set to ``boolector``,
  ``dv-solve``, or ``auto``. Defaults to ``boolector``.
* **Programmatically** via :func:`vsc.set_solver_backend`, which overrides the
  environment value:

  .. code-block:: python

     import vsc
     vsc.set_solver_backend("boolector")   # force Boolector
     print(vsc.get_solver_backend())        # -> "boolector"
     vsc.set_solver_backend(None)           # clear override; use VSC_SOLVER/default

The ``auto`` value resolves to the first available back-end (preferring
``dv-solve`` once present, falling back to ``boolector``).

Available back-ends
====================

``boolector``
   The historical PyVSC engine (SMT bit-vector solver, ``pyboolector``).
   Always available when ``pyboolector`` is installed. Supports soft
   constraints; distribution (``dist``) is expanded into ordinary constraints
   before solving.

``dv-solve``
   Native finite-domain (CLP/FD) engine. *(Introduced incrementally; see the
   integration notes under* ``doc/notes`` *for current coverage.)*

Behavioral notes
================

* **Random stability is per-engine.** A fixed PyVSC seed reproduces the same
  value stream *within a given back-end*; switching back-ends changes the
  sequence. Cross-engine value equality is not a goal.
