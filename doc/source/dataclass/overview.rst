########
Overview
########

``vsc.dc`` (imported as ``vdc``) is a second way to write PyVSC classes: as
Python dataclasses, with fields declared by annotation and constraints written
as ordinary Python.

.. literalinclude:: ../../../examples/dc/01_alu_txn.py
   :language: python
   :start-after: import vsc.dc as vdc
   :end-before: def main():

Compared with the classic API (``@vsc.randobj``, :doc:`../constraints`):

* **Fields are dataclass fields.** An instance holds plain Python values
  (ints, enum members, lists); there are no field objects to unwrap.
* **Constraints are parsed, not run.** A constraint body is read once per
  class, when the class is defined, so Python constructs can mean what they
  say: ``and``, ``if``, ``for`` and ``in`` are constraints, and a construct with
  no constraint meaning is an error at that point, with its file and line.
  Classic constraint methods run on every randomization, so ``and`` or ``if``
  cannot work there.
* **Structure is built once per class** and reused by every instance, which
  makes vdc faster than the classic API on repeated randomization.
* **The same solvers and coverage model.** vdc builds the same models as the
  classic API and solves them with the same back-ends (:doc:`../solver_backends`);
  covergroups report through the same UCIS export.

Contents of this section:

* :doc:`rand_classes`: fields, types, arrays, nested objects, randomization
  methods.
* :doc:`constraints`: writing constraints, by task.
* :doc:`constraint_grammar`: every accepted and rejected construct.
* :doc:`inline_constraints`: ``randomize_with``.
* :doc:`generic_constraints`: named, parameterized constraint blocks.
* :doc:`coverage`: covergroups.
* :doc:`porting`: moving a classic class to vdc.

The runnable examples are in ``examples/dc/``; the test suite runs each one.
