"""
``vsc.sphinx`` — a Sphinx extension for documenting pyvsc classes.

Enable it with ``extensions = ["sphinx.ext.autodoc", "vsc.sphinx"]``. Plain
``automodule`` / ``autoclass`` then document ``@vdc.dataclass`` rand classes
and covergroups as what they are: fields with widths and domains, constraints
with their bodies and the fields they read, coverpoints with their bins,
crosses with their components. Classic ``@vsc.randobj`` classes get their
constraints documented, and with ``vsc_classic_instantiate`` their fields;
classic ``@vsc.covergroup`` classes, with it, their coverpoints and crosses.

``.. autorandclass::`` / ``.. autocovergroup::`` are ``autoclass`` with
per-class options; ``.. py:randclass::``, ``py:randfield``, ``py:constraint``,
``py:covergroup``, ``py:coverpoint`` and ``py:cross`` can be written by hand.

Configuration (``conf.py``), each also a directive option
``:<object>-<option>:`` on the ``auto*`` directives::

    vsc_autodoc_enable = True              # enrich automodule/autoclass output
    vsc_randclass_hide_paramlist = False   # drop the __init__ parameter list
    vsc_randclass_summary = "table"        # "table" | "list" | "none"
    vsc_randclass_member_groups = "fields, constraints, generics"
    vsc_randclass_show_mode_hint = False
    vsc_field_show_constraints = True
    vsc_field_show_domain = True
    vsc_constraint_show_source = "body"    # "body" | "collapsed" | "none"
    vsc_constraint_show_fields = True
    vsc_constraint_signature_fields = False  # c_op » op, a, b
    vsc_constraint_show_refs = True
    vsc_covergroup_summary = "table"       # "table" | "list" | "none"
    vsc_coverpoint_show_bins = True
    vsc_coverpoint_show_options = True
    vsc_cross_show_selections = True
    vsc_type_style = "alias"               # "alias" (u4) | "sv" | "words"
    vsc_covergroup_elaborate = True        # exact bin counts (elaborate.py)
    vsc_classic_instantiate = False        # construct classic classes

Design: ``doc/notes/sphinx_extension_design.md``.
"""


def setup(app):
    from . import directives, domain, events, render

    app.setup_extension("sphinx.ext.autodoc")

    for name, default in render.DEFAULTS.items():
        app.add_config_value("vsc_" + name, default, "env")

    domain.setup_domain(app)
    app.add_directive("autorandclass", directives.AutoRandClass)
    app.add_directive("autocovergroup", directives.AutoCovergroup)

    app.connect("source-read", events.reset_docstring_state)
    app.connect("autodoc-process-docstring", events.process_docstring)
    app.connect("autodoc-skip-member", events.skip_member)
    app.connect("autodoc-process-signature", events.process_signature)
    app.connect("doctree-read", events.retype_classes)
    app.connect("missing-reference", events.width_type_reference)

    from vsc.__version__ import _pkg_version
    return {
        "version": _pkg_version,
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
