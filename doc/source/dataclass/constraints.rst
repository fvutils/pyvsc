###################
Writing Constraints
###################

A constraint is a method decorated with ``@vdc.constraint``. Its body is a
list of statements that must all hold after ``randomize()``. The body is
written in Python, but it is **parsed, not executed**: each statement is read
as the constraint it spells, once per class, when the class is defined.

.. code-block:: python

    import vsc.dc as vdc

    @vdc.dataclass
    class Txn(vdc.RandClass):
        a: vdc.u8 = vdc.rand()
        b: vdc.u8 = vdc.rand()

        @vdc.constraint
        def c(self):
            self.a < self.b
            self.a + self.b == 200

Because the body is parsed, Python constructs mean what they say: ``and`` is
logical and, ``for`` loops over an array, ``x in {1, 2, 3}`` is membership, and
``if`` makes a conditional constraint. Anything that has no constraint meaning
(an assignment, a ``print``, a call to your own function) is an error when the
class is defined, with the file and line.

This page is a tour by task. :doc:`constraint_grammar` is the complete list.
Every example on this page is a runnable file under ``examples/dc/``.

Comparisons and arithmetic
==========================

The comparison operators, ``+ - * // %``, ``& | ^ ~``, ``<< >>``, ``**`` with a
constant exponent, unary ``-``, ``abs``, and ``min``/``max`` of several values
all work as expected, with one difference from Python: fields have a fixed
width, so arithmetic follows SystemVerilog's width rules (an 8-bit sum is taken
at 32 bits when compared with a literal, signed ``//`` truncates, ``>>`` is
logical). The details are in :ref:`the reference <widths>`.

Comparisons chain as in Python: ``1 <= self.size <= 8``.

Logic: ``and``, ``or``, ``not``, ``if``
=======================================

.. literalinclude:: ../../../examples/dc/07_grammar_logic.py
   :language: python
   :start-after: # [logic-start]
   :end-before: # [logic-end]

* ``and``, ``or`` and ``not`` are logical. A field used as a truth value is
  tested with ``!= 0``.
* ``~`` is the bitwise invert, not logical not. Write ``not``.
* An ``if`` without ``else`` is an implication: when the condition holds, the
  body must; otherwise the body is free.
* ``x if c else y`` works as an expression, too.

``&`` and ``|`` also combine comparisons, but mind Python's precedence:
``a > 3 & a < 6`` reads as ``a > (3 & a) < 6``. vdc rejects that form and asks
for ``(a > 3) & (a < 6)`` or ``a > 3 and a < 6``.

``match`` works on enum and constant values:

.. literalinclude:: ../../../examples/dc/07_grammar_logic.py
   :language: python
   :start-after: # [match-start]
   :end-before: # [match-end]

Sets: ``in``
============

.. literalinclude:: ../../../examples/dc/08_grammar_sets.py
   :language: python
   :start-after: # [sets-start]
   :end-before: # [sets-end]

.. important::

   ``range(lo, hi)`` is half-open, as in Python. ``vdc.r[lo:hi]`` is inclusive,
   as SystemVerilog's ``inside {[lo:hi]}``. Inside a list, a pair ``(lo, hi)``
   is an inclusive range: ``self.a in [(1, 5), 9]``.

The classic spellings, ``self.a.inside(vdc.rangelist(1, 2, (10, 20)))`` and
``.not_inside(...)``, still work and take the same sets. So does ``self.a in
self.arr``, which means "equal to one of the array's elements".

Arrays
======

A field annotated ``list[...]`` is an array: ``vdc.rand(size=N)`` for a fixed
size, ``vdc.rand(max_size=M)`` for a random size up to ``M``.

.. literalinclude:: ../../../examples/dc/09_grammar_arrays.py
   :language: python
   :start-after: # [arrays-start]
   :end-before: # [arrays-end]

* ``for x in self.arr``, ``for i in range(len(self.arr))`` and ``for i, x in
  enumerate(self.arr)`` constrain every element. Loops nest.
* ``for`` over a constant (``range(4)``, a module-level tuple) is unrolled: the
  body once per value.
* ``len``, ``sum`` and ``math.prod`` are the size, sum and product.
* ``all(cond for x in self.arr)`` and ``any(...)`` work as statements and in
  expressions (``any`` not yet over a random-size array of scalars).
* ``self.arr[-1]`` counts from the end, and ``self.arr[self.i]`` with a random
  ``i`` selects the element the solver picks for ``i``.
* ``self.a[7:4]`` on a scalar is a SystemVerilog part-select, high bit first.
  Slicing an array is not supported.

Soft constraints, distributions, ordering, uniqueness
=====================================================

These are statement helpers:

.. code-block:: python

    @vdc.constraint
    def c(self):
        vdc.soft(self.len == 4)                     # unless something conflicts
        vdc.dist(self.kind, [vdc.weight(0, 10),     # value 0, weight 10
                             vdc.weight((1, 3), 80),
                             vdc.weight(4, 10)])
        vdc.solve_order(self.mode, self.addr)       # choose mode first
        vdc.unique(self.a, self.b, self.c)          # all different

A ``dist`` weight may be a non-random field, read at each solve:
``vdc.weight(1, self.en_one)``.

Constants
=========

A name a constraint reads that is not a field (a module constant, a closure
variable, an enum member, a class attribute) is read when the class is defined.
A class attribute is read per subclass, so a subclass can change a limit
without repeating the constraint:

.. literalinclude:: ../../../examples/dc/11_class_constants.py
   :language: python
   :start-after: # [const-start]
   :end-before: # [const-end]

Named collections work with ``in`` and ``for`` the same way.

Reusing constraints
===================

A constraint method of a subclass with the same name replaces the base class's
(override by name), and ``set_constraint_mode("name", False)`` turns one off
for an object. To name a block of constraints and apply it only where it is
referenced, possibly with parameters, use a generic constraint
(:doc:`generic_constraints`).

What a constraint cannot contain
================================

A constraint body is not run, so it cannot hold anything that only makes sense
when run: assignments, local variables, ``print``, calls to your own functions,
``while``, ``assert``, ``try``. Each is rejected when the class is defined. For
a reusable computation, use a value generic (``@vdc.constraint.value``,
:doc:`generic_constraints`).
