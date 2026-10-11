#####################
Randomizable Classes
#####################

A randomizable class is a ``@vdc.dataclass`` that inherits ``vdc.RandClass``:

.. code-block:: python

    import vsc.dc as vdc

    @vdc.dataclass
    class AluTxn(vdc.RandClass):
        op:  vdc.u4  = vdc.rand()          # 4-bit unsigned, random
        a:   vdc.u32 = vdc.rand()
        tag: vdc.u8  = vdc.field(default=0)  # state: not randomized

    txn = AluTxn()
    txn.randomize()

Field types
===========

The annotation gives a field's width and signedness:

* ``vdc.u1`` ... ``vdc.u64``: unsigned, 1 to 64 bits.
* ``vdc.s1`` ... ``vdc.s64``: signed.
* ``vdc.bitv`` with ``vdc.rand(width=N)``: a width chosen at run time.
* An ``Enum`` or ``IntEnum`` class: an enumerated field. Solved values are
  written back as members.
* ``int``: 32-bit signed.
* ``list[T]``: an array of ``T`` (see `Arrays`_).
* Another ``RandClass``: a nested object (see `Nested objects`_).

Field declarations
==================

``vdc.rand(...)``
   A random field. Keyword arguments:

   * ``domain=``: the values the field may take, as a property of the field
     rather than a constraint: ``(lo, hi)`` (inclusive), ``range(lo, hi)``
     (half-open), a list such as ``[1, 2, (100, 200)]``, a ``vdc.rangelist``,
     or a weighted ``{value_or_range: weight}`` dict. On an array it applies
     to every element. A bad domain fails when the class is defined.
   * ``size=N``: a fixed-size array.
   * ``max_size=M``: a random-size array of at most ``M`` elements.
   * ``width=``, ``signed=``: override the annotation (needed with
     ``vdc.bitv``).
   * ``default=``, ``default_factory=``: the initial value.

``vdc.randc(...)``
   A cyclic random field: it takes every value its constraints allow, in a
   random order, before repeating one. Same arguments as ``rand``.

``vdc.field(...)``
   A plain field the solver does not assign. Constraints may read it; its
   value at the time of ``randomize()`` is used. A ``list`` field declared this
   way is a table the solver reads (its length may differ between instances).

Arrays
======

.. code-block:: python

    @vdc.dataclass
    class Pkt(vdc.RandClass):
        payload: list[vdc.u8] = vdc.rand(size=8)       # 8 elements
        tags:    list[vdc.u8] = vdc.rand(max_size=8)   # 0 to 8 elements

        @vdc.constraint
        def c(self):
            for x in self.payload:
                0x61 <= x <= 0x7a
            2 < len(self.tags) <= 6

After ``randomize()``, a random-size array holds as many elements as its
solved size. :doc:`constraints` shows what constraints can say about arrays.

Enums
=====

.. code-block:: python

    from enum import IntEnum, auto

    class Op(IntEnum):
        ADD = 0
        SUB = auto()
        AND = auto()

    @vdc.dataclass
    class T(vdc.RandClass):
        op:  Op = vdc.rand()
        ops: list[Op] = vdc.rand(size=4)

        @vdc.constraint
        def c(self):
            self.op != Op.AND
            for o in self.ops:
                o in {Op.ADD, Op.SUB}

Nested objects
==============

A field annotated with another ``RandClass`` is a nested object, randomized
with its parent; ``list[Sub]`` is an array of them. Constraints reach into
them: ``self.base.addr == 0``, ``for r in self.regs: r.addr < 0x100``,
``self.regs[self.i].addr == 4``. A nested object declared with ``vdc.field()``
keeps its values. The nested class's own constraints apply too.

.. literalinclude:: ../../../examples/dc/03_nested.py
   :language: python
   :start-after: import vsc.dc as vdc
   :end-before: def main():

Randomizing
===========

``obj.randomize()``, or ``vdc.randomize(obj)``
   Solve all random fields. Raises ``vdc.SolveFailure`` when the constraints
   cannot all hold.

``obj.randomize_with()``, or ``vdc.randomize_with(obj)``
   A context manager adding constraints for one call; see
   :doc:`inline_constraints`.

``obj.set_rand_mode("name", False)``
   Hold a field at its current value; ``get_rand_mode`` reads the setting.

``obj.set_constraint_mode("name", False)``
   Turn off a named constraint for this object; ``get_constraint_mode`` reads
   it.

``obj.set_randstate(rs)``, ``obj.get_randstate()``
   The random state (``vsc.RandState``), for reproducible sequences.

``pre_randomize(self)`` / ``post_randomize(self)``
   Define these methods to run code before and after each solve.
   ``post_randomize`` sees the solved values, and changes it makes stay.

Inheritance
===========

A subclass inherits fields and constraints. A constraint method with the same
name as a base-class one replaces it. Class attributes that constraints read
are read per subclass (:doc:`constraints`).
