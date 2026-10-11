Methodology
===========

How the numbers on :doc:`index` are measured, and how to reproduce one. The
harness is ``benchmarks/perf/`` in the pyvsc repository; its module docstrings
are the detailed reference.

What is measured
----------------

An **arm** is a front-end, a solver back-end and a build of the code:

.. list-table::
   :header-rows: 1
   :widths: 1 3

   * - Arm
     - What it is
   * - ``classic-btor``
     - ``@vsc.randobj`` classes, Boolector back-end, this commit
   * - ``classic-dvs``
     - ``@vsc.randobj`` classes, dv-solve back-end, this commit
   * - ``dc-btor``
     - dataclass (``vsc.dc``) classes, Boolector back-end, this commit
   * - ``dc-dvs``
     - dataclass classes, dv-solve back-end, this commit
   * - ``stock``
     - pyvsc 0.9.5 and pyboolector exactly as installed from PyPI. It never
       changes, so it anchors every run and its spread measures the noise.
   * - ``cr``
     - constrainedrandom 1.3.0, the external reference, on the workloads it can
       express

A **workload** is one randomization problem written once per front-end, the way
a user would write it, with a plain-Python check of its constraints that shares
no code with pyvsc. Its source is hashed into the run's manifest, so editing a
constraint starts a new trend line rather than silently changing the problem.

A **pattern** is how the workload is driven: ``cold`` constructs a fresh object
and randomizes it once (the sequence-item and generator pattern, where the
front-end matters most); ``warm`` randomizes one object repeatedly.

How a cell is timed
-------------------

Each (workload, arm, pattern) cell runs in a fresh Python process pinned to its
own physical core, with that arm's build on its path, so no cell inherits
another's caches. In the process:

#. 20 untimed warm-up calls;
#. up to 300 calls whose results are checked against the workload's oracle
   (one wrong answer invalidates the run);
#. a batch size chosen so one batch takes at least 0.3 s of CPU;
#. five timed batches, garbage collector on, as users run it; the cell's time is
   the **minimum CPU time per call** over the batches;
#. 100 more checked calls.

The whole suite runs twice, in an interleaved order, and each cell keeps its
faster round: a neighbour that is busy for a few seconds can't survive a second
measurement taken a minute later.

Ratios and scores
-----------------

Every ratio divides two arms measured in the same run on the same machine:

* **T** = classic-btor / dc-dvs: what the whole new stack buys;
* **B** = classic-btor / classic-dvs: what the dv-solve back-end buys;
* **F** = classic-dvs / dc-dvs: what the dataclass front-end buys;
* **S** = stock / dc-dvs and **S0** = stock / classic-btor: today against
  pyvsc 0.9.5, with and without changing any code.

A suite score is the geometric mean of a ratio over the workloads, with
workload families (scalar, distribution, composite, arrays) weighted and no
family allowed more than 40% of the score. A cell that is ``n/a``, failed or
timed out never enters a ratio.

Each run also records two calibration kernels (a pure-Python loop and a fixed
Boolector solve loop) and the machine class, so a change of machine or
interpreter is visible rather than mistaken for a change in pyvsc. Runs on a
busy host are marked; the history keeps bad runs too, flagged.

riscv-dv
--------

The ``riscv-dv`` suite runs someone else's real program: the Python generator
(``pygen``) of `riscv-dv <https://github.com/chipsalliance/riscv-dv>`_, which
models RISC-V instructions as ``@vsc.randobj`` classes and randomizes one per
generated instruction, mostly with inline ``randomize_with()`` constraints. It
uses the classic front-end, so it measures what an existing pyvsc user gets
without changing their code: the latest release (pyvsc 0.9.6 from PyPI),
today's pyvsc on Boolector, and today's pyvsc on dv-solve.

- **Test.** ``riscv_arithmetic_basic_test`` with its testlist options
  (``instr_cnt=10000``, one numeric-corner directed stream), target
  ``rv32imc``. It is the one test riscv-dv's own CI runs on pygen; the other
  testlist entries stop inside pygen on every pyvsc version (unported
  features). riscv-dv is pinned to one commit in ``tools.lock.json``.
- **Process.** Each (seed, arm) generates one program in a fresh process,
  calling the test's ``_run_phase`` directly rather than through ``run.py``
  and pygen's process pool, so only generation is timed (not Python start-up
  or imports). Every (seed, arm) runs twice and keeps the faster; both runs
  must write byte-identical programs.
- **Metric.** CPU time per generated instruction (instruction lines in the
  ``.S``), pooled over the seeds. pygen draws the main program's length at
  random, so the length differs per seed and per arm, and a per-program time
  would compare different amounts of work.
- **Two riscv-dv fixes**, applied when the child imports pygen, never to
  riscv-dv's files: a stand-in for the ``imp`` module, which Python 3.12
  removed; and ``get_rand_instr`` honouring its exclude lists, as SV
  riscv-dv does. Without the second, the numeric-corner stream draws
  compressed instructions it excluded, among them ``c.addi16sp``, whose
  ``rd == sp`` contradicts the stream's own register list. pyvsc 0.9.6 only
  completed that ``randomize_with()`` because it ignored the register list.
- **Correctness.** The child re-checks the solver's answers in plain
  Python. After every instruction's ``randomize_with()`` it checks the inline
  register constraints (operands inside the stream's ``avail_regs``, ``rd``
  off the reserved registers) and that the stream's ``avail_regs`` size still
  matches its contents. Every instruction's own constraints are checked too:
  the shift-amount masks, the compressed-format register sets, and the
  nonzero-immediate and no-hint rules. So are the numeric-corner stream's
  register list (ten unique registers, none reserved or zero) and its sizes.
  Today's arms must
  have no violation and first pass a validation run with dv-solve's own model
  check and its Boolector cross-check on; the release is recorded as it
  behaves, with its violation count beside its time.

Reproducing a number
--------------------

From a pyvsc checkout with its development environment (dv-solve built in
``packages/dv-solve``):

.. code-block:: bash

   # all suites, about three minutes; writes build/perf/runs/<name>.json.gz
   PYTHONPATH=benchmarks python3 -m perf.collect --kind manual --suites core

   # one cell by hand
   PYTHONPATH=src:benchmarks python3 -P benchmarks/perf/child.py \
       '{"workload": "alu", "frontend": "dc", "backend": "dv-solve", "pattern": "cold"}'

   # the riscv-dv suite, about 10 minutes
   PYTHONPATH=benchmarks python3 -m perf.collect --kind manual --suites riscv-dv

   # a quick look, nothing recorded: two seeds, short programs
   PYTHONPATH=benchmarks python3 -m perf.riscv_dv --seeds 999,1 --instr-cnt 1000

``stock``, ``stock-0.9.6`` and ``cr`` are side-installed, and riscv-dv checked
out, under ``build/perf/builds/`` on first use, pinned in
``benchmarks/perf/tools.lock.json``.

Where the data lives
--------------------

Each run's full record is kept as a build artifact. Its compact summary, one
line per run with every cell's time, is committed to
``benchmarks/history/<year>.jsonl`` by ``perf.consolidate``, and this page is
rendered from those files when the documentation is built.
