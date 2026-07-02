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
  ``dv-solve``, or ``auto``. Read once at import time. Defaults to
  ``boolector``.
* **Programmatically** via the Python API below, which overrides the
  environment value.

The ``auto`` value resolves to the first available back-end (preferring
``dv-solve`` once present, falling back to ``boolector``).

Python API
----------

.. py:function:: vsc.set_solver_backend(name)

   Select the solver back-end programmatically. ``name`` is one of
   ``"boolector"``, ``"dv-solve"``, or ``"auto"``. The choice takes precedence
   over ``VSC_SOLVER``. Pass ``None`` to clear the override and fall back to
   ``VSC_SOLVER`` (or the built-in default). An unknown name raises when the
   next ``randomize()`` resolves the back-end.

.. py:function:: vsc.get_solver_backend()

   Return the effective back-end name -- the programmatic override if one is
   set, otherwise the ``VSC_SOLVER`` value (or the default).

The override is re-read on **every** ``randomize()`` call, so it can be changed
at any point and takes effect immediately; there is no need to set it before
constructing randomized objects.

.. code-block:: python

   import vsc
   vsc.set_solver_backend("dv-solve")    # force dv-solve
   print(vsc.get_solver_backend())       # -> "dv-solve"
   ...
   vsc.set_solver_backend(None)          # clear override; use VSC_SOLVER/default

The precedence, highest first, is: programmatic override
(:func:`vsc.set_solver_backend`) → ``VSC_SOLVER`` → built-in default
(``boolector``).

Available back-ends
====================

``boolector``
   The historical PyVSC engine (SMT bit-vector solver, ``pyboolector``).
   Always available when ``pyboolector`` is installed. Supports soft
   constraints; distribution (``dist``) is expanded into ordinary constraints
   before solving.

``dv-solve``
   Native finite-domain engine. It pairs two solvers internally (see
   *How dv-solve decides* below). Supports soft constraints and handles
   distribution (``dist``) **natively** — each ``dist`` becomes one weighted
   native value-selection (per-value ``:=`` / per-range ``:/`` / zero-weight
   exclusion) rather than being expanded into ordinary constraints. A few
   ``dist`` shapes still defer to the fallback: ``dist`` over array elements,
   conditional/multiple ``dist`` on one field, and ``dist`` on a field wider
   than 64 bits. An implication/``if`` whose **guard** combines comparisons over
   lifted arithmetic (e.g. ``((b-1) >= 4) & ((b-1) < 8) -> ...``) also defers, so
   it is solved correctly by the fallback rather than risk an unsound native
   model. *(Introduced incrementally; see the integration notes under*
   ``doc/notes`` *for current coverage.)*

How dv-solve decides
====================

The ``dv-solve`` back-end owns **two** solving engines and chooses between them
per RandSet:

* **Primary — bounds-propagation search.** Fast, and the source of good
  *stimulus distribution* (uniform marginals via fair value picking, plus
  weighted ``dist``). This solves the overwhelming majority of RandSets.
* **Completeness fallback — internal BV-SAT engine** (bit-blasting + a bundled
  SAT solver). It is *complete*, so it is **authoritative for both SAT and
  UNSAT**. When the primary engine cannot give a trustworthy answer — a
  compile-time UNSAT, a construct it cannot compile, or a search that returns no
  solution — dv-solve runs the *same* problem through the BV-SAT engine.

On that fallback:

* **UNSAT** from BV-SAT is a sound proof, so dv-solve reports a genuine solve
  failure **without** consulting the external Boolector back-end. dv-solve is
  now authoritative for unsatisfiability on its own.
* **SAT** from BV-SAT confirms the problem is solvable, but the BV-SAT engine's
  *model distribution* is clustered (good for "find a solution", not for
  coverage stimulus). By default dv-solve therefore defers the actual value
  selection for such a RandSet to the distribution-preserving fallback rather
  than emitting BV-SAT's biased model.

Soft constraints
================

dv-solve serves ``soft`` constraints **natively on both engines** — no Boolector
is required for soft.

* **Semantics.** A ``soft`` constraint is a *preference*: it is satisfied when
  possible and **relaxed** (dropped) when it conflicts with the hard constraints
  or with a higher-priority soft. Relaxation is engine-owned (dv-solve decides
  which softs to drop); pyvsc never enforces a soft as a hard constraint. Soft
  preference follows **declaration order**: a soft declared *later* is preferred
  over (kept harder than) one declared earlier, so among mutually-conflicting
  softs the last-declared survives — the standard SystemVerilog ``soft`` override
  rule. Both the primary and the BV-SAT serve paths use the same
  priority-respecting *greedy* relaxation, in the same order, matching the
  Boolector back-end — including its one well-known limitation: when several
  equally-preferred softs participate in a conflict, greedy relaxation may drop
  more of them than the theoretical optimum. The relaxation order is stable across
  repeated ``randomize()`` calls (incl. the plan-cache / problem-reuse fast paths).

* **Guarded / conditional softs.** ``with if_then(g): soft(e)`` (and the
  ``implies`` / ``if/else`` forms) are honored natively: the soft is preferred
  only when its guard holds.

* **Force-served RandSets.** A soft-bearing RandSet that routes to the BV-SAT
  engine (e.g. a conjunctive guarded body, or a field wider than 64 bits) is
  served by dv-solve's soft-aware MaxSAT — the kept soft set is enforced while
  the well-distributed sampler draws the remaining free fields. Softs are never
  silently dropped on this path.

Environment toggles (advanced / debugging)
------------------------------------------

* ``VSC_DVSOLVE_BVSAT=0`` — disable the internal BV-SAT engine entirely
  (revert to deferring un-decidable RandSets to the external fallback).
* ``VSC_DVSOLVE_BVSAT_SERVE_SAT=1`` — let BV-SAT also *serve* satisfiable
  fallback problems (write their values). Off by default because its
  distribution is not uniform; intended for non-coverage uses or once a uniform
  sampler is added.
* ``VSC_DVSOLVE_NO_FALLBACK=1`` — strict mode: the Randomizer raises instead of
  falling back to another back-end on ``BackendIncomplete``, so any residual
  dependence on the fallback (e.g. Boolector) surfaces loudly. A diagnostic for
  enumerating which constructs still defer; off by default.
* ``VSC_DVSOLVE_FALLBACK_TALLY=1`` — collect a process-global histogram of
  fallback reason codes across a run (queryable via
  ``vsc.model.randomizer.get_fallback_tally()``), without enabling full
  profiling. The burn-down dashboard for dv-solve self-sufficiency. Off by
  default (zero overhead).
* ``VSC_DVSOLVE_PLAN_CACHE=0`` / ``VSC_DVSOLVE_REUSE=0`` — disable the pre-solve
  plan cache / per-RandSet compiled-problem reuse (e.g. to isolate a suspected
  stale-cache issue). Both reuse paths are byte-identical to a fresh build.

Cross-checking against Boolector (recommended during adoption)
--------------------------------------------------------------

While Boolector remains the default back-end, the surest way to gain confidence
in (and report bugs against) dv-solve is to run your existing, Boolector-validated
regression under dv-solve with **XCHECK** enabled — a differential cross-check
that re-verifies every model dv-solve produces against Boolector::

    VSC_SOLVER=dv-solve VSC_DVSOLVE_XCHECK=1 python -m pytest ...

For each RandSet dv-solve solves, XCHECK confirms the model satisfies the
constraints (membership) and that the SAT/UNSAT verdict agrees with Boolector. It
compares *semantic agreement*, never exact values (value streams legitimately
differ between engines), and consumes no ``randstate`` (it checks the model
dv-solve already produced — it does not re-solve). A disagreement raises
``XCheckMismatch`` with the offending model and constraints.

* ``VSC_DVSOLVE_XCHECK=1`` — enable the cross-check (off by default; adds the cost
  of a Boolector build + solve per RandSet).
* ``VSC_DVSOLVE_XCHECK_WARN=1`` — log + tally mismatches instead of raising, so a
  long run surfaces *all* disagreements rather than aborting on the first.
* ``VSC_DVSOLVE_XCHECK_RATE=p`` — cross-check a strided fraction ``0 < p <= 1`` of
  RandSets (deterministic / reproducible), to bound the 2× cost on large suites.

Running a regression under both back-ends
=========================================

Because ``VSC_SOLVER`` is read at import time, exercising a regression under a
different back-end means running it in a fresh process with the env var set::

    VSC_SOLVER=boolector python -m pytest ...
    VSC_SOLVER=dv-solve  python -m pytest ...

The repository ships a helper that runs the full ``ve/unit`` suite once per
back-end and fails if either leg fails::

    ve/run_all_backends.sh            # whole suite, both back-ends
    ve/run_all_backends.sh -k array   # extra args are forwarded to pytest

The ``dv-solve`` leg is skipped (with a warning, not a failure) when the
``dv-solve`` library is not importable, so the script is usable in a
Boolector-only checkout. The project CI mirrors this with a ``VSC_SOLVER``
matrix, so every change is validated under both back-ends.

Behavioral notes
================

* **Random stability is per-engine.** A fixed PyVSC seed reproduces the same
  value stream *within a given back-end*; switching back-ends changes the
  sequence. Cross-engine value equality is not a goal.
* **Distribution on the BV-SAT path.** A RandSet served by the BV-SAT engine
  (only when ``VSC_DVSOLVE_BVSAT_SERVE_SAT=1``) has weaker distribution than the
  primary/Boolector path and does not honor soft-constraint preferences. This is
  intentional — the BV-SAT engine exists for *completeness* (deciding hard
  SAT/UNSAT), not for distribution.
