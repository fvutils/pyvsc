############################
Constraint Grammar Reference
############################

This page lists every Python construct a vdc constraint body may contain, what
it means, and every construct that is rejected, with the message you get. It
applies to the bodies of ``@vdc.constraint``, ``@vdc.constraint.generic`` and
``@vdc.constraint.value``, and to ``randomize_with`` bodies (see
:doc:`inline_constraints` for what differs there).

For a tutorial introduction, see :doc:`constraints`.

The rule
========

A constraint body is **parsed, never executed**. Inside it, a Python construct
means its constraint counterpart wherever one exists with the same meaning, and
is rejected everywhere else, when the class is defined, with the file and line
of the offending construct. There is no third outcome: nothing is silently
accepted with a different meaning.

Two consequences follow:

* Where Python and SystemVerilog read a construct differently, the Python
  reading wins: ``and`` is logical and, ``range(a, b)`` is half-open,
  ``x in coll`` is membership.
* Arithmetic follows the solver's fixed-width rules (SystemVerilog), because
  fields are fixed-width. See `Widths and signedness`_.

Each row below carries an ID (``G-nn``). The tests in
``ve/unit_dc/test_constraint_grammar.py`` are named after these IDs, so a bug
report can name the row.

Literals and names
==================

.. list-table::
   :header-rows: 1
   :widths: 8 30 62

   * - ID
     - Construct
     - Meaning
   * - G-01
     - Integer literal: ``0x10``, ``0b101``, ``0o17``, ``1_000``
     - The integer.
   * - G-02
     - Negative literal: ``-5``
     - The integer.
   * - G-03
     - ``True`` / ``False`` in an expression
     - 1 / 0.
   * - G-06
     - Module-level name: ``self.a == LIMIT``
     - Its value, read when the class is defined. An int, bool or enum
       member.
   * - G-07
     - Closure variable (the class is defined inside a function)
     - Its value, read when the class is defined.
   * - G-08
     - Enum member: ``self.e == Op.ADD``
     - The member.
   * - G-09
     - Class attribute through ``self``: ``self.a < self.MAX``
     - The class attribute, read **per subclass**: a subclass that overrides
       ``MAX`` gets its own value in the inherited constraint.
   * - G-10
     - Class attribute through the class's own name: ``self.a < T.MAX``
     - The same as ``self.MAX``, per subclass.

Arithmetic and bitwise operators
================================

.. list-table::
   :header-rows: 1
   :widths: 8 30 62

   * - ID
     - Construct
     - Meaning
   * - G-13
     - ``//``, ``%``
     - Integer division and remainder. **Truncating** (toward zero) on signed
       values, as in SystemVerilog, not flooring as in Python:
       ``-7 // 2 == -3``, ``-7 % 2 == -1``.
   * - G-14
     - ``+``, ``-``, ``*``
     - Fixed-width arithmetic (see `Widths and signedness`_).
   * - G-15
     - ``x ** k``
     - ``x`` multiplied by itself ``k`` times. ``k`` must be a constant from 0
       to 8.
   * - G-17
     - ``&``, ``|``, ``^``
     - Bitwise. On comparison results they act as logical operators, but see
       G-24.
   * - G-18
     - ``<<``, ``>>``
     - Shifts. ``>>`` is **logical** (zero-filling), as in SystemVerilog.
   * - G-19
     - ``~x``
     - Bitwise invert, taken at the expression's width: ``~a == 0xF0`` with an
       8-bit ``a`` widens ``a`` to 32 bits first, so it never holds. Write
       ``(~a & 0xFF) == 0xF0``. Use ``not`` for logical negation.
   * - G-20
     - Unary ``-x``
     - ``0 - x``. Its value is Python's: ``-a`` of an unsigned 8-bit ``a`` is
       in ``-255..0``, never ``0xFF``.
   * - G-21
     - Unary ``+x``
     - ``x``.

Logical operators
=================

.. list-table::
   :header-rows: 1
   :widths: 8 30 62

   * - ID
     - Construct
     - Meaning
   * - G-22
     - ``a and b``, ``a or b``
     - Logical and / or. An operand that is not a truth value is tested with
       ``!= 0``. Python's short-circuit and value-returning behavior do not
       apply. As a whole statement, ``a and b`` is the two statements ``a`` and
       ``b``.
   * - G-23
     - ``not x``
     - Logical not (``x == 0`` for a non-boolean operand).
   * - G-25
     - ``x if c else y``
     - A select. As a statement it is ``if c: x`` / ``else: y``.
   * - G-61
     - ``bool(x)``
     - ``x != 0``.

Comparisons
===========

.. list-table::
   :header-rows: 1
   :widths: 8 30 62

   * - ID
     - Construct
     - Meaning
   * - G-26
     - ``==``, ``!=``, ``<``, ``<=``, ``>``, ``>=``
     - Comparison.
   * - G-27
     - Chain: ``1 < a < 5``, ``a == b == c``
     - The pairwise conjunction, as in Python. As a whole statement, each pair
       is its own statement.
   * - G-28
     - ``in`` / ``not in`` inside a chain: ``0 < a in S``
     - ``(0 < a) and (a in S)``, as in Python.
   * - G-30
     - A literal on the left: ``5 == self.a``
     - As written.

Set membership
==============

``x in <set>`` and ``x not in <set>``. ``x.inside(<set>)``,
``x.not_inside(<set>)`` and ``x.outside(<set>)`` take the same sets (G-42).

.. list-table::
   :header-rows: 1
   :widths: 8 34 58

   * - ID
     - Set
     - Meaning
   * - G-31
     - List or tuple literal: ``[1, 3, self.b, self.c + 1]``
     - The values listed; entries may be fields or expressions.
   * - G-32
     - ``(lo, hi)`` inside a list: ``[(1, 5), 9]``
     - The range ``lo..hi``, **inclusive**. A top-level tuple is a set of
       values: ``a in (1, 5)`` is ``a`` is 1 or 5.
   * - G-33
     - Set literal: ``{1, 2, 3}``
     - The values listed.
   * - G-34
     - ``range(hi)``, ``range(lo, hi)``
     - **Half-open**, as in Python: ``range(1, 4)`` is 1, 2, 3.
   * - G-35
     - ``range(lo, hi, step)``
     - ``lo``, ``lo + step``, ... below ``hi``. ``step`` must be a non-zero
       constant.
   * - G-36
     - ``vdc.r[lo:hi]``, ``vdc.r[a:b, c:d]``
     - **Inclusive** ranges, as SystemVerilog's ``inside {[lo:hi]}``.
   * - G-37
     - ``vdc.rangelist(...)``, ``vdc.rng(lo, hi)``
     - The classic pyvsc spelling.
   * - G-38
     - An array field: ``self.a in self.arr``
     - ``a`` equals one of the array's elements (those within its solved size,
       for a random-size array).
   * - G-39
     - A named constant collection (module, closure or class attribute: a
       list, tuple, set, frozenset or range)
     - Its values, read when the class is defined (per subclass for a class
       attribute).
   * - G-40
     - A starred constant collection: ``[*ALLOWED, 9]``
     - Its values, and the others listed.

Fields, arrays and reductions
=============================

.. list-table::
   :header-rows: 1
   :widths: 8 34 58

   * - ID
     - Construct
     - Meaning
   * - G-44
     - Bit-select: ``self.a[3]``, ``self.a[self.i]``
     - The bit; a random index selects symbolically.
   * - G-45
     - Part-select: ``self.a[7:4]``
     - Bits 7 down to 4, **high bit first, inclusive** (SystemVerilog order).
       This is not a Python slice: ``self.a[4:7]`` is rejected.
   * - G-47
     - Element: ``self.arr[1]``
     - The element.
   * - G-48
     - Negative index: ``self.arr[-1]``
     - Counted from the end, as in Python, also for a random-size array
       (``self.arr[self.arr.size - 1]``).
   * - G-49
     - Random index: ``self.arr[self.i]``
     - The element the solved index selects.
   * - G-51
     - Nested objects: ``self.sub.x``, ``self.objs[1].x``,
       ``self.objs[self.i].x``
     - The field.
   * - G-52
     - ``self.arr.size``, ``self.arr.sum``
     - The array's size and the sum of its elements.
   * - G-53
     - ``len(self.arr)``
     - ``self.arr.size``.
   * - G-54
     - ``sum(self.arr)``
     - ``self.arr.sum``.
   * - G-55
     - ``self.arr.product``, ``math.prod(self.arr)``
     - The product of the elements.
   * - G-56
     - ``min(a, b, ...)``, ``max(a, b, ...)`` of two or more scalars
     - The smallest / largest.
   * - G-58
     - ``abs(x)``
     - ``x`` if ``x >= 0``, else ``-x``. An unsigned expression is never
       negative, so ``abs(a - b)`` of unsigned fields is ``a - b`` (which
       wraps, as in SystemVerilog).
   * - G-59
     - ``all(<cond> for x in self.arr)``
     - Every element satisfies ``cond``. As a statement it is a ``for`` loop.
   * - G-60
     - ``any(<cond> for x in self.arr)``
     - Some element satisfies ``cond``. Not yet supported over a random-size
       scalar array; use ``v in self.arr`` there.
   * - G-65
     - ``self.name(...)``: a generic constraint
     - See :doc:`generic_constraints`.

The loops ``all``/``any`` accept are those of the ``for`` statement (G-70 to
G-72), with optional ``if`` filters.

Statements
==========

.. list-table::
   :header-rows: 1
   :widths: 8 34 58

   * - ID
     - Statement
     - Meaning
   * - G-67
     - A boolean expression
     - A hard constraint.
   * - G-68
     - A bare field: ``self.flag``
     - ``self.flag != 0``.
   * - G-69
     - ``True`` / ``False``
     - No constraint / unsatisfiable.
   * - G-70
     - ``for x in self.arr:``
     - ``foreach`` over the elements.
   * - G-71
     - ``for i in range(len(self.arr)):``, ``for i in range(self.arr.size):``
     - ``foreach`` over the indices.
   * - G-72
     - ``for i, x in enumerate(self.arr):``
     - Both.
   * - G-73
     - ``for o in self.objs:`` (an array of objects)
     - ``foreach``; ``o.x`` reads the element's fields.
   * - G-74
     - ``for v in <constant iterable>:`` (``range(N)`` of constants, a named or
       literal collection; tuple targets allowed)
     - The body once per value, with the name a constant in it. At most 1024
       iterations.
   * - G-75
     - Nested ``for``
     - Nested loops. A loop name exists only inside its body.
   * - G-78
     - ``if`` / ``elif`` / ``else``
     - Conditional constraints. An ``if`` without ``else`` is an implication.
   * - G-79
     - ``if`` with ``and`` / ``or`` / ``not`` / a field
     - As in expressions (G-22, G-23, G-68).
   * - G-80
     - ``match`` / ``case``
     - An ``if`` / ``elif`` chain. Patterns: literal, constant or enum values,
       ``|`` alternatives, and ``_``.
   * - G-81
     - ``with vdc.if_then(c):`` / ``vdc.else_if`` / ``vdc.else_then``
     - The classic spelling of ``if`` / ``elif`` / ``else``.
   * - G-82
     - ``with vdc.implies(c):``
     - Implication.
   * - G-83
     - ``with vdc.foreach(self.arr, idx=..., it=...) as ...:``
     - The classic spelling of ``for``.
   * - G-85
     - ``vdc.soft(e)``, ``vdc.unique(...)``, ``vdc.solve_order(a, b)``,
       ``vdc.dist(x, [vdc.weight(v, w), ...])``
     - Soft constraint, all-different, solve ordering, weighted distribution.
   * - G-86 to G-88
     - ``pass``, a docstring or string, ``...``
     - Ignored.
   * - G-92
     - ``return <expr>`` as the only statement of a value generic
     - See :doc:`generic_constraints`.

Rejected constructs
===================

Each of these is an error when the class is defined (for a ``randomize_with``
body, when the ``with`` is entered, before the body could run), naming the file
and line. The last column is part of the message.

.. rejected-start

.. list-table::
   :header-rows: 1
   :widths: 8 40 52

   * - ID
     - Construct
     - Message
   * - G-04
     - A string, bytes, float, complex or ``None`` constant
     - ``unsupported constant``
   * - G-05
     - An f-string
     - ``unsupported expression``
   * - G-11
     - A name that is not a field, constant or loop name
     - ``not supported in constraints``
   * - G-12
     - True division ``/``
     - ``integer constraints have no true division; use '//'``
   * - G-15
     - ``**`` with a non-constant exponent, or one outside 0..8
     - ``needs a constant exponent from 0 to``
   * - G-16
     - ``@``
     - ``unsupported binary operator``
   * - G-24
     - ``a > 3 & a < 6``: ``&``, ``|`` or ``^`` as an unparenthesized operand of
       a comparison chain (Python reads it as ``a > (3 & a) < 6``)
     - ``binds tighter than``
   * - G-29
     - ``is`` / ``is not``
     - ``unsupported comparison``
   * - G-41
     - An enum class as a set: ``self.e in E``
     - ``value set must be``
   * - G-43
     - A call as a set: ``self.a in helper(1)``
     - ``unsupported call``
   * - G-46
     - A part-select with a step or a missing bound
     - ``part-select with a step``
   * - G-50
     - An array slice: ``self.arr[0:2]``
     - ``array slices are not supported``
   * - G-57
     - ``min(self.arr)``, ``max(self.arr)`` (not supported yet)
     - ``over an array is not supported yet``
   * - G-62
     - ``int(x)``, ``float(x)``, ``str(x)`` and other conversions
     - ``unsupported call in expression``
   * - G-63
     - A list, set or dict comprehension; a generator outside ``all``/``any``
     - ``unsupported expression``
   * - G-64
     - A call to your own function: ``helper(self.a)``
     - ``unsupported call in expression``
   * - G-66
     - ``lambda``, ``:=``, ``await``, ``yield``
     - ``unsupported expression``
   * - G-76
     - A ``for`` over anything else (``zip``, ``reversed``, a slice, a
       call). A ``for`` with ``else``, and ``break`` or ``continue``, get
       messages of their own.
     - ``a constraint loop runs over an array field``
   * - G-77
     - ``while``
     - ``unsupported statement``
   * - G-84
     - A ``with`` that is not a vdc helper, or with several items
     - ``unsupported with-context``
   * - G-89
     - Assignment: ``self.a = 5``, ``self.a += 1``
     - ``a constraint is not an assignment``
   * - G-90
     - A local variable: ``lo = self.b + 1``
     - ``local variables are not supported``
   * - G-91
     - ``assert c``
     - ``'assert' is not a constraint``
   * - G-93
     - ``raise``, ``try``, ``import``, ``del``, ``global``, ``nonlocal``, a
       nested ``def`` or ``class``
     - ``unsupported statement``

.. rejected-end

.. _widths:

Widths and signedness
=====================

Fields are fixed-width, and expressions follow SystemVerilog's rules, on both
solver back-ends:

* An expression is evaluated at its **context width**: the widest operand, and
  a 32-bit width for an integer literal. ``a + b == 300`` with 8-bit ``a`` and
  ``b`` is satisfiable, because the sum is taken at 32 bits.
* ``~`` inverts at the context width (G-19).
* An expression with a signed and an unsigned operand is **unsigned**: the
  signed operand is read as its bit pattern. With a signed 8-bit ``s`` and an
  unsigned 8-bit ``b``, ``s == b`` holds for ``s = -56, b = 200``, and
  ``s < b`` never holds for a negative ``s``.
* ``-`` of an unsigned value can wrap: ``a - b < 0`` is never true for unsigned
  ``a`` and ``b``.
* Signed ``//`` and ``%`` truncate toward zero, and ``>>`` is logical (G-13,
  G-18).

See :doc:`../solver_backends` for the back-ends.

Things to watch for
===================

.. important::

   ``range(lo, hi)`` is **half-open** (Python), but ``vdc.r[lo:hi]`` and a
   ``(lo, hi)`` pair in a list are **inclusive** (SystemVerilog). ``a in (1, 5)``
   is the set {1, 5}; ``a in [(1, 5)]`` is the range 1..5.

.. important::

   ``self.a[7:4]`` is a SystemVerilog part-select, high bit first. It is not a
   Python slice.

.. note::

   Constants (module names, closure variables, class attributes) are read when
   the class is defined. A class attribute is read for each subclass. In a
   ``randomize_with`` body, values from the caller are read on every call
   instead (:doc:`inline_constraints`).

.. note::

   The builtins ``len``, ``sum``, ``min``, ``max``, ``abs``, ``all``, ``any``,
   ``bool``, ``range`` and ``enumerate`` are recognized only when your module
   does not define its own name with that name.

Not supported yet
=================

* ``min(self.arr)`` / ``max(self.arr)`` (G-57): constrain an auxiliary field
  with a ``for`` loop instead.
* ``any(...)`` / ``all(...)`` used in an expression (not as a statement), and
  ``any(...)`` anywhere, over a **random-size scalar** array (G-60): use
  ``v in self.arr`` or a ``for`` loop.
* Local variables (G-90).
* ``match`` capture, class, mapping and sequence patterns, and guards (G-80).
