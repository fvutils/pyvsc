########
Coverage
########

A covergroup is a ``@vdc.dataclass`` that inherits ``vdc.Covergroup``.
Coverpoints are fields annotated ``vdc.Coverpoint[T]``, and crosses are fields
annotated ``vdc.Cross``. The coverage semantics are IEEE 1800-2023 §19, and
vdc covergroups report through the same model and UCIS export as classic ones
(:doc:`../coverage`).

.. literalinclude:: ../../../examples/dc/04_coverage.py
   :language: python
   :start-after: import vsc.dc as vdc
   :end-before: def main():

.. code-block:: python

    cov = AluCov()
    cov.sample(Op.ADD, 0)          # push coverpoints, in declaration order
    print(cov.get_coverage())      # cumulative (type) coverage
    print(cov.get_inst_coverage()) # this instance

Coverpoints
===========

Push coverpoint
   ``vdc.coverpoint()`` with no ``ref``. Its value is passed to ``sample()``
   (by position, or by name), or set with ``cov.op.set(v)``.

Pull coverpoint
   ``vdc.coverpoint(ref=lambda s: <expr>)``, evaluated from the covergroup's
   state when it is sampled: an arithmetic expression, or a read through a
   ``cg_arg`` (below).

Bins
   ``bins=dict(name=vdc.bin(...), ...)``, with ``vdc.bin(v, ...)`` for values
   and ranges, ``vdc.bin_array(n, ...)`` for ``n`` bins over a range, and
   ``vdc.wildcard_bin(...)``. Without ``bins``, bins are automatic from the
   ``Coverpoint[T]`` width or the enum's members (``option.auto_bin_max`` caps
   the width-derived ones). ``ignore_bins=`` and ``illegal_bins=`` take the same
   specs. ``iff=lambda s: ...`` guards a coverpoint.

Sampling inputs
===============

``vdc.cg_arg()``
   A binding to an external object, given at construction:
   ``TxnCov(txn=t)``. Pull coverpoints read it.

``vdc.sample_arg()``
   A persistent sample formal that feeds pull coverpoints.

A custom ``sample()``
   Override ``sample()`` to extract values yourself, then call
   ``self.assign_from(src)`` and ``super().sample()``.

The synthesized ``sample()`` has the covergroup's real signature (push
coverpoints in declaration order, then ``sample_arg`` fields), so
``inspect.signature(cov.sample)`` and editor completion show them, and a wrong
call raises Python's own ``TypeError``. A formal you leave out keeps its
previous value. Static type checkers cannot see this generated signature; for
checker-visible code, set the typed ``sample_arg`` attributes and call
``cov.sample()``, or use ``assign_from(src)``.

Crosses
=======

``vdc.cross(lambda s: s.a, lambda s: s.b)`` crosses coverpoints; a cross of
crosses flattens to its component coverpoints.

A cross's ``ignore_bins`` and ``illegal_bins`` select cross bins with
``vdc.binsof`` (IEEE 1800 §19.6): ``vdc.binsof(s.a)`` selects a component, and
``.intersect([...])`` narrows it to values and ``(lo, hi)`` ranges. ``&``,
``|`` and ``~`` combine selections. Ignored cross bins are left out of the
coverage; illegal ones are left out and their hits are counted separately.

.. literalinclude:: ../../../examples/dc/06_cross_binsof.py
   :language: python
   :start-after: import vsc.dc as vdc
   :end-before: def main():

``binsof`` must name a component of the same cross. Selecting a named bin
(``binsof(s.a.lo)``) is not supported yet; narrow with ``.intersect(...)``.

The randomize-and-sample loop
=============================

.. literalinclude:: ../../../examples/dc/05_crv_loop.py
   :language: python
   :start-after: import vsc.dc as vdc
