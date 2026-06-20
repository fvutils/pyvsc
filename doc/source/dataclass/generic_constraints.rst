###################
Generic Constraints
###################

.. note::

   This page documents the **dataclass front-end** (``import vsc.dc as vdc``).
   For the classic ``@vsc.randobj`` equivalent (``dynamic_constraint``) see
   :doc:`../constraints`.

A *fixed* constraint (``@vdc.constraint``) always holds. A *generic* constraint
holds **only when it is referenced** — by name, from a fixed constraint. Generic
constraints let you give a name (and, optionally, parameters) to a block of
constraints and then *select* or *compose* those blocks, rather than baking every
scenario into one always-on block (PSS 3.1 §13.1.1).

Generic constraints come in two forms, declared with nested decorators:

* ``@vdc.constraint.generic`` — a named *boolean* constraint block.
* ``@vdc.constraint.value`` — a *value* (expression) generic, used in expression
  position like a function (also inferred from a single ``return``).

.. note::

   **Porting from classic pyvsc:** a classic ``@vsc.dynamic_constraint`` is
   exactly a vdc **no-parameter** ``@vdc.constraint.generic``. The vdc front-end
   adds *parameterized* and *value* generics, which have no classic equivalent.


Referencing a generic
=====================

A generic is applied wherever it is referenced from a fixed constraint. There are
two reference contexts:

**Statement reference** — the reference stands alone; the generic's *entire body*
is spliced into the enclosing scope::

    @vdc.dataclass
    class my_c(vdc.RandClass):
        a: vdc.u8 = vdc.rand()
        b: vdc.u8 = vdc.rand()

        @vdc.constraint.generic
        def both(self):
            self.a < 20
            self.b > 200

        @vdc.constraint
        def use(self):
            self.both()          # applies a < 20 AND b > 200

**Boolean reference** — the reference appears inside an expression (``|``, ``&``,
``~``, an ``if`` condition); the block stands for the conjunction of its items and
can be composed with boolean operators.

.. important::

   Reference a generic with **parentheses** when using it as a boolean term
   (``self.foo()``), so it is not mistaken for a field access.


Boolean composition (PSS Example 136)
=====================================

The canonical use is selecting one of several mutually-exclusive scenarios and
letting the solver choose, with full look-ahead::

    @vdc.dataclass
    class send_pkt(vdc.RandClass):
        pkt_sz: vdc.u16 = vdc.rand()

        @vdc.constraint
        def pkt_sz_c(self):
            self.pkt_sz > 0

        @vdc.constraint.generic
        def small_pkt_c(self):
            self.pkt_sz <= 100

        @vdc.constraint.generic
        def jumbo_pkt_c(self):
            self.pkt_sz > 1500

        @vdc.constraint
        def interesting_sz_c(self):
            self.small_pkt_c() | self.jumbo_pkt_c()

Each ``randomize()`` produces a ``pkt_sz`` in ``[1..100]`` *or* ``[1501..]``. This
is something classic SystemVerilog constraints cannot express directly — ``||``
there is a boolean-expression operator, not a way to OR two constraint *blocks*.

.. note::

   ``a() | b()`` is a plain disjunction: the solver returns *any* satisfying
   value, it does **not** promise a fair split between the branches. When the two
   windows differ greatly in size, the wider one dominates. Use ``vdc.dist`` (in a
   referenced statement-position generic) if you need to shape the distribution.


Parameterized generics
=======================

A generic may take parameters in addition to ``self`` (a method with parameters is
*always* generic — a fixed constraint has nothing to bind them to). Parameters make
a generic a reusable, named *relation template*::

    @vdc.dataclass
    class my_c(vdc.RandClass):
        x: vdc.u16 = vdc.rand()

        @vdc.constraint
        def in_window(self, lo, hi):
            self.x >= lo
            self.x <= hi

        @vdc.constraint
        def pick(self):
            self.in_window(10, 20) | self.in_window(100, 110)

Actual arguments may be constants *or other random fields* — e.g.
``self.aligned(self.addr, self.region_align)`` — giving relations parameterized by
other solved values. Parameters support positional and **keyword** arguments and
**default values**::

    @vdc.constraint
    def in_window(self, lo, hi=110):
        self.x >= lo
        self.x <= hi

    @vdc.constraint
    def pick(self):
        self.in_window(10, hi=20) | self.in_window(lo=100)   # hi defaults to 110


Value generics
==============

A generic whose body is a single ``return <expr>`` is a *value* generic: it is
inlined as an expression wherever it is referenced, and remains relational (unlike
a classic function call, which is pre-evaluated)::

    @vdc.dataclass
    class my_c(vdc.RandClass):
        sz: vdc.u16 = vdc.rand()

        @vdc.constraint
        def aligned(self, n):
            return (self.sz // n) * n

        @vdc.constraint
        def align_c(self):
            self.sz == self.aligned(8)
            self.sz > 0

Because a value generic's body is ordinary Python, it is *dual-use*: after a solve
the same method computes the value against the concrete field values, so
``obj.aligned(8)`` is also a valid post-solve accessor::

    it.randomize()
    assert it.sz == it.aligned(8)     # readback matches what the solver chose


Referencing in ``randomize_with``
=================================

A generic may also be referenced inside an inline ``randomize_with`` block, to
apply it for a single solve — the analog of a classic ``dynamic_constraint``
reference. Use ``()`` and combine with ``|`` just as in a fixed constraint::

    it = send_pkt()

    with it.randomize_with() as h:
        h.small_pkt_c()                    # this solve: pkt_sz <= 100

    with it.randomize_with() as h:
        h.small_pkt_c() | h.jumbo_pkt_c()  # this solve: small OR jumbo

Parameterized generics may be referenced inline with **constant** actuals
(``it.window(100, 110)``); a field-valued actual must be referenced from a
``@vdc.constraint`` instead.

.. note::

   Inline references reify the generic as a boolean term, so the generic's body
   must be boolean (as in the boolean-position rule above).


Inheritance
===========

Generic constraints follow the same MRO override-by-name rule as fixed
constraints: a subclass generic of the same name *shadows* the base one, and new
generics are added. A reference resolves to the most-derived definition. An
override that *changes the kind* of a constraint (e.g. fixed in the base, generic
in the subclass) emits a warning, since it silently flips whether the constraint
is always-on.


Errors caught at class-definition time
======================================

References are validated when the ``@vdc.dataclass`` is defined (not at solve
time), so mistakes fail fast:

* **Referencing a fixed constraint** is an error — you have referenced something
  that already always holds, so you almost certainly meant it to be generic. The
  error tells you to mark it ``@vdc.constraint.generic``.
* **Referencing an unknown name** (or a field) is an error.
* **Reference cycles** (``a`` → ``b`` → ``a``) are rejected.
* **Boolean position requires a boolean body.** A generic referenced under
  ``|``/``&``/``~``/``if`` may contain only boolean items (relations, ``inside``,
  ``implies``, ``if``/``else``, ``unique``, nested references). A generic that
  contains ``soft``/``dist``/``solve_order``/``foreach`` can still be referenced as
  a *statement*, but not as a boolean term.
