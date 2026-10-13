##################################
Documenting Classes with Sphinx
##################################

.. note::

   This page documents the **dataclass front-end** (``import vsc.dc as vdc``).
   Classic ``@vsc.randobj`` classes get their constraints documented the same
   way; their fields are created in ``__init__`` and are not visible without
   running it.

A ``@vdc.dataclass`` class already knows a great deal a reader needs: the
width and kind of each field, its domain, each constraint and the fields it
reads, each coverpoint and its bins, each cross and its components. The
``vsc.sphinx`` extension puts that into your Sphinx documentation, so plain
``automodule`` / ``autoclass`` document constraints, fields, coverpoints and
crosses as what they are rather than as ordinary attributes and methods.


Enabling it
===========

Add the extension next to autodoc in ``conf.py``::

    extensions = [
        "sphinx.ext.autodoc",
        "vsc.sphinx",
    ]

Sphinx 7, 8 and 9 are supported. Nothing else is needed: an ``automodule``
of a module containing rand classes and covergroups now produces the output
shown in `Example`_ below.


What is documented
==================

For a **rand class**:

* A summary: a table of fields (type, kind, domain or size, the constraints
  that read each one) and a table of constraints.
* Each **field**, as a ``rand`` / ``randc`` / state entry with its type
  (``u4``, ``s16``, an enum or a nested class), domain, array size and the
  constraints that read it.
* Each **constraint**, with its docstring, its **body as written**, the fields
  it reads and the generic constraints it references. Generic and value
  constraints show their parameters and the constraints that reference them,
  and are listed in their own group.
* The class signature, with ``Annotated[int, _Width(4, unsigned)]`` shown as
  ``u4``.

For a **covergroup**:

* The synthesized ``sample()`` with its real arguments.
* The sampling inputs (``vdc.cg_arg`` / ``vdc.sample_arg`` fields).
* Each **coverpoint**: the sampled type, whether it is pushed (and its position
  in ``sample()``) or pulled (with the sampled expression), its ``iff`` guard, a
  table of bins (or how automatic bins are formed), ignore and illegal bins,
  options, and the crosses that use it.
* Each **cross**: its components, and its ignore and illegal selections written
  out as ``binsof`` expressions.

Everything is cross-linked: a field links to the constraints that read it, a
constraint to the fields it reads, a coverpoint to the crosses over it.

The pyvsc base-class machinery (``randomize``, ``set_rand_mode``,
``get_coverage``, ...) is never repeated on each class. Your own methods,
including ``pre_randomize`` / ``post_randomize``, are documented as usual.


Where the descriptions come from
================================

=====================  =======================================================
Object                 Description
=====================  =======================================================
Class, constraint      its docstring
Field, coverpoint,     a ``#:`` comment before or after it, or a string just
cross                  after it — the usual Sphinx attribute convention
Bin                    ``doc="..."`` on ``vdc.bin`` / ``vdc.bin_array`` /
                       ``vdc.wildcard_bin``; otherwise a ``#`` comment on the
                       bin's line, or comment lines just above it
Cross selection        a ``#`` comment on its line, or just above it
=====================  =======================================================

For example::

    length: vdc.u16 = vdc.rand(domain=(1, 4096))
    """Transfer length in bytes."""

    length: vdc.Coverpoint[vdc.u16] = vdc.coverpoint(
        bins=dict(
            single=vdc.bin_array([1], (1, 4)),     # one beat
            long=vdc.bin_array([1], (257, 4096), doc="Longer, up to a page."),
        ))

``doc=`` is ignored by coverage; it exists for documentation only.


Configuration
=============

Set these in ``conf.py``. The defaults are shown.

.. list-table::
   :header-rows: 1
   :widths: 35 12 53

   * - Setting
     - Default
     - Meaning
   * - ``vsc_autodoc_enable``
     - ``True``
     - enrich ``automodule`` / ``autoclass`` output
   * - ``vsc_randclass_hide_paramlist``
     - ``False``
     - drop the ``__init__`` parameters from the class signature
   * - ``vsc_randclass_summary``
     - ``"table"``
     - ``"table"``, ``"list"`` or ``"none"``
   * - ``vsc_randclass_member_groups``
     - see below
     - order of the field / constraint / generic groups
   * - ``vsc_randclass_show_mode_hint``
     - ``False``
     - a line about ``set_rand_mode`` / ``set_constraint_mode``
   * - ``vsc_field_show_constraints``
     - ``True``
     - "Constrained by" on fields
   * - ``vsc_field_show_domain``
     - ``True``
     - domains and array sizes
   * - ``vsc_constraint_show_source``
     - ``"body"``
     - ``"body"``, ``"collapsed"`` (an HTML ``<details>``) or ``"none"``
   * - ``vsc_constraint_show_fields``
     - ``True``
     - "Reads" on constraints
   * - ``vsc_constraint_signature_fields``
     - ``False``
     - also show the fields read in the signature, ``c_op » op, a, b``
   * - ``vsc_constraint_show_refs``
     - ``True``
     - generics used / referenced by
   * - ``vsc_covergroup_summary``
     - ``"table"``
     - ``"table"``, ``"list"`` or ``"none"``
   * - ``vsc_coverpoint_show_bins``
     - ``True``
     - bins, ignore and illegal tables
   * - ``vsc_coverpoint_show_options``
     - ``True``
     - coverage options
   * - ``vsc_cross_show_selections``
     - ``True``
     - ignore / illegal ``binsof`` selections
   * - ``vsc_type_style``
     - ``"alias"``
     - ``"alias"`` (``u4``), ``"sv"`` (``bit [3:0]``) or ``"words"`` (``4-bit unsigned``)

``vsc_randclass_member_groups`` defaults to ``"fields, constraints,
generics"``. Ordinary methods always follow the pyvsc groups.


Per-class options
=================

``automodule`` and ``autoclass`` can only use the ``conf.py`` settings. For
one class, use ``autorandclass`` or ``autocovergroup``: they take every
``autoclass`` option, plus each setting above as an option without the
``vsc_`` prefix and with dashes::

    .. autorandclass:: mypkg.DmaDesc
       :members:
       :constraint-show-source: collapsed
       :randclass-summary: none

    .. autocovergroup:: mypkg.DmaCov
       :coverpoint-show-bins: false


Inheritance
===========

A subclass's entry documents what the subclass defines. Fields and
constraints inherited from a base class appear in its summary tables and link
to the base class's entries. With ``:inherited-members:`` they are documented
in full on the subclass, marked "Inherited from". A constraint that overrides
a base-class constraint links to the one it overrides.


Linking to members
==================

Fields, constraints, coverpoints and crosses are ordinary Python objects to
Sphinx, so the usual roles find them — ``:py:obj:`DmaDesc.c_page```,
``:py:attr:`DmaDesc.length```. Each kind also has its own role:
``:py:randclass:``, ``:py:randfield:``, ``:py:constraint:``,
``:py:covergroup:``, ``:py:coverpoint:`` and ``:py:cross:``.

The same object types can be written by hand, for example in a design
note::

    .. py:randclass:: Pkt
       :module: handmade

       .. py:randfield:: len
          :kind: randc
          :type: u6
          :constrained-by: c_len

       .. py:constraint:: c_len
          :reads: len

          Length is short.


Example
=======

The module below is documented on this page with a plain ``automodule``.

.. literalinclude:: dma_doc_example.py
   :language: python
   :lines: 7-

.. rubric:: Output

.. automodule:: dma_doc_example
   :members:
   :undoc-members:
