##################
Inline Constraints
##################

``randomize_with()`` adds constraints for one call:

.. code-block:: python

    txn = Txn()
    with txn.randomize_with() as it:
        it.a == 5
        it.b > it.a

The block is solved when it ends, with the class's own constraints and the
ones written in it. ``it`` stands for the object; after the block, ``txn`` (and
``it``) hold the solved values. ``vdc.randomize_with(txn)`` is the same.

The body is parsed, not run
===========================

A ``randomize_with`` body follows the same grammar as a ``@vdc.constraint`` body
(:doc:`constraint_grammar`), with ``it`` in place of ``self``: ``and``, ``or``,
``not``, ``if``, ``for``, ``match`` and ``x in coll`` mean the same thing in
both places. vdc reads the body's source when the ``with`` is entered, and the
body itself never runs. A grammar error is raised then, before anything in the
body could happen, with the file and line.

Values from the caller
======================

Unlike a ``@vdc.constraint`` body, an inline body usually reads the caller's
variables: a base address, a list of allowed values, a flag. Any part of the
body that names neither ``it`` nor a loop over ``it`` is a **host expression**:
plain Python, evaluated once per call, in the caller's scope.

.. literalinclude:: ../../../examples/dc/10_inline.py
   :language: python
   :start-after: # [inline-start]
   :end-before: # [inline-end]

Here ``self.base + 4 * i``, ``self.window()``, ``self.allowed``, ``read_only``
and ``(3, 5)`` are host expressions. Their rules:

* A host value must be an int, a bool or an enum member. On the right of
  ``in`` it may also be a collection (list, tuple, set, frozenset or range), and
  as a ``for`` iterable any iterable of those. A value of another type raises
  ``TypeError`` naming the expression and its line.
* A host expression may call functions (``self.window()`` above). It runs
  exactly once per ``randomize_with``.
* A mistake in a host expression raises Python's own error (``NameError``,
  ``AttributeError``, ...), with the body's file and line in the traceback.
* An ``if`` on host values only (``if read_only:``) decides its branch per
  call, as if the body ran.
* Where the grammar needs a constant (an ``**`` exponent, part-select bounds, a
  ``range`` step), a host value may be used; when it changes from one call to
  the next, the body is parsed again for the new value.
* ``T.a``, where ``a`` is a field of class ``T``, is the class attribute (the
  field's default value), not the field. Write ``it.a``.

Rules that apply only inline
============================

* Every statement must name ``it`` (or a loop name bound over it). A statement
  that does not, such as ``log.append(x)``, constrains nothing; it is rejected
  rather than run.
* Passing ``it`` itself to a function (``add_rules(it)``) is the one case where
  the body does run: the function adds constraints through ``it``, on the
  operator path described below.
* You cannot step into the body with a debugger; it is not run.

Generic constraints work inline as in a class body, with host expressions as
arguments: ``it.window(lo, lo + 10)``, ``it.x == it.twice(k)``, ``it.small() or
it.large()``. See :doc:`generic_constraints`.

When the source cannot be read
==============================

A body whose source vdc cannot find (code passed to ``exec``, ``python -c``)
runs instead, on the operator path that pyvsc's classic API uses: ``it.a``
builds an expression object, and each statement records its constraint. On this
path ``&``, ``|``, ``vdc.if_then`` and ``vdc.foreach`` work, but ``and``,
``or``, ``not`` and ``if`` cannot: Python tests the expression for truth, which
would drop a constraint. vdc raises ``TypeError`` there instead. ``x in
vdc.rangelist(...)`` works on both paths.

The environment variable ``VSC_DC_INLINE_PARSE=0`` selects the operator path
for every body.

Moving from the operator path
=============================

Until pyvsc 2.0 a ``randomize_with`` body ran on the operator path. A body
written for it behaves differently when parsed:

* ``it.a / 2`` was silently integer division; it is now an error (use ``//``).
* ``it.a > 3 and it.a < 6`` kept only ``it.a < 6``; it now means both.
* ``not``, ``if``/``else`` and ``x if c else y`` on constraint expressions were
  silently wrong; they now mean what they say.
* A ``for`` loop over a Python list ran once per element with Python values; it
  still does (a host iterable is unrolled), and a ``for`` over ``it.arr`` is now
  a ``foreach``.
* A statement that does not mention ``it`` is now an error.

To keep the old behavior while migrating, set ``VSC_DC_INLINE_PARSE=0``.
