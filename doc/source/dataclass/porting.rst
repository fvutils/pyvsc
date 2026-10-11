############################
Porting from the Classic API
############################

A classic ``@vsc.randobj`` class and its vdc equivalent:

.. literalinclude:: ../../../examples/dc/12_porting.py
   :language: python
   :start-after: # [classic-start]
   :end-before: # [classic-end]

.. literalinclude:: ../../../examples/dc/12_porting.py
   :language: python
   :start-after: # [vdc-start]
   :end-before: # [vdc-end]

Both satisfy the same checks (``examples/dc/12_porting.py`` runs them).

Equivalents
===========

.. list-table::
   :header-rows: 1
   :widths: 45 55

   * - Classic
     - vdc
   * - ``@vsc.randobj`` class with fields set in ``__init__``
     - ``@vdc.dataclass`` class inheriting ``vdc.RandClass``, fields annotated
   * - ``self.a = vsc.rand_uint8_t()``
     - ``a: vdc.u8 = vdc.rand()``
   * - ``vsc.rand_int16_t()``, ``vsc.rand_bit_t(5)``
     - ``vdc.s16``, ``vdc.u5``
   * - ``vsc.uint8_t(3)`` (not random)
     - ``vdc.field(default=3)``
   * - ``vsc.rand_list_t(vsc.uint8_t(), 4)``
     - ``list[vdc.u8] = vdc.rand(size=4)``
   * - ``vsc.randsz_list_t(vsc.uint8_t())``
     - ``list[vdc.u8] = vdc.rand(max_size=M)``
   * - ``vsc.rand_enum_t(E)``
     - ``e: E = vdc.rand()``
   * - ``x.inside(vsc.rangelist(1, (2, 5)))``
     - ``x in [1, (2, 5)]`` (or ``x.inside(vdc.rangelist(...))``)
   * - ``with vsc.if_then(c):`` / ``else_if`` / ``else_then``
     - ``if c:`` / ``elif`` / ``else``
   * - ``with vsc.implies(c):``
     - ``if c:`` (no ``else``), or ``vdc.implies``
   * - ``with vsc.foreach(self.arr, idx=True) as i:``
     - ``for i in range(len(self.arr)):``
   * - ``(a > 1) & (a < 5)``, ``~(a == 3)``
     - ``a > 1 and a < 5``, ``not (a == 3)`` (``&`` still works; ``~`` is
       bitwise only)
   * - ``vsc.soft``, ``vsc.dist``/``vsc.weight``, ``vsc.solve_order``,
       ``vsc.unique``
     - ``vdc.soft``, ``vdc.dist``/``vdc.weight``, ``vdc.solve_order``,
       ``vdc.unique``
   * - ``@vsc.dynamic_constraint``
     - ``@vdc.constraint.generic`` (:doc:`generic_constraints`)
   * - ``with vsc.randomize_with(obj):`` / ``with obj.randomize_with() as it:``
     - ``with obj.randomize_with() as it:``
   * - ``@vsc.covergroup``
     - ``vdc.Covergroup`` (:doc:`coverage`)

Differences to watch
====================

* **Python meanings.** ``range(lo, hi)`` excludes ``hi``; ``vdc.r[lo:hi]`` and
  a ``(lo, hi)`` pair in a list include it, as classic ``rangelist`` does.
* **``~`` is bitwise.** A classic constraint often writes ``~(a == 3)`` for
  "not". That still works on a comparison, but ``~`` of a field inverts its
  bits at the expression's width; write ``not``.
* **Constants are read once.** A classic constraint method runs on every
  randomization, so it can read a variable that changes. A vdc constraint is
  read when the class is defined. Put a value that changes per call in a
  non-random field (``vdc.field()``) and constrain against the field, or pass
  it in a ``randomize_with`` body, which reads caller values on every call.
* **No Python in constraints.** A classic constraint may compute with Python
  (``x == helper(3)``) because it runs; vdc rejects calls to your own
  functions. Compute the value first, or use a value generic.
* **Values are plain.** ``obj.a`` is an int (or enum member, or list), not a
  field object; there is no ``.get_val()``.
