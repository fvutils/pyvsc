"""
pyvsc object types on the Sphinx Python domain.

Adds ``py:randclass``, ``py:randfield``, ``py:constraint``, ``py:covergroup``,
``py:coverpoint`` and ``py:cross``. Each is a subclass of the stock Python
directive for the same kind of Python object (class, attribute, method), so
nesting, full names, ``:py:obj:`` / ``:py:attr:`` resolution and intersphinx
work unchanged. The facts about the object (kind, type, the fields a
constraint reads, ...) are directive options, rendered by the directive, so
generated reST stays plain and the directives are usable by hand.

See ``doc/notes/sphinx_extension_design.md`` §5.2.
"""
import re

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx import addnodes
from sphinx.domains import ObjType
from sphinx.domains.python import PyAttribute, PyClasslike, PyMethod, PyXRefRole
from sphinx.locale import _


# objtype -> (label, stock roles first, stock CSS class)
OBJECT_TYPES = {
    "randclass": (_("rand class"), ("class", "obj", "randclass"), "class"),
    "covergroup": (_("covergroup"), ("class", "obj", "covergroup"), "class"),
    "randfield": (_("rand field"), ("attr", "obj", "randfield"), "attribute"),
    "constraint": (_("constraint"), ("meth", "obj", "constraint"), "method"),
    "coverpoint": (_("coverpoint"), ("attr", "obj", "coverpoint"), "attribute"),
    "cross": (_("cross"), ("attr", "obj", "cross"), "attribute"),
}


_TITLE_TARGET = re.compile(r"^(.+?)\s*<([^<>]+)>$")


def _names(arg):
    """A comma-separated option value -> list of names."""
    return [n.strip() for n in (arg or "").split(",") if n.strip()]


def _keyword(text):
    return [addnodes.desc_sig_keyword("", text), addnodes.desc_sig_space()]


class _VscObjectMixin:
    """Shared rendering: an xref to a sibling member, and a field list of facts
    appended to the content."""

    def _xref(self, target, text=None, reftype="obj"):
        """A pending reference resolved like ``:py:obj:`target``` written in
        this object's class body. ``target`` may be ``title <target>``, or
        ``!name`` for the name without a link."""
        if target.startswith("!"):
            # Sphinx's convention: show the name, do not link it.
            return nodes.literal(target[1:], target[1:], classes=["xref", "py"])
        m = _TITLE_TARGET.match(target)
        if m and text is None:
            text, target = m.group(1).strip(), m.group(2).strip()
        env = self.env
        modname = self.options.get("module", env.ref_context.get("py:module"))
        clsname = env.ref_context.get("py:class")
        node = addnodes.pending_xref(
            "", nodes.literal(text or target, text or target, classes=["xref", "py"]),
            refdomain="py", reftype=reftype, reftarget=target,
            refexplicit=text is not None, refwarn=False)
        node["py:module"] = modname
        node["py:class"] = clsname
        return node

    def _xref_list(self, names):
        para = nodes.paragraph()
        for i, n in enumerate(names):
            if i:
                para += nodes.Text(", ")
            para += self._xref(n)
        return para

    def _fact(self, label, body):
        if isinstance(body, str):
            body = nodes.paragraph("", body)
        return nodes.field("", nodes.field_name("", label),
                           nodes.field_body("", body))

    def _facts(self):
        """[(label, str or node)] to show below the description."""
        return []

    def transform_content(self, contentnode):
        super().transform_content(contentnode)
        facts = [f for f in self._facts() if f is not None]
        if facts:
            fl = nodes.field_list(classes=["vsc-facts"])
            for label, body in facts:
                fl += self._fact(label, body)
            # After the prose and any code, before generated tables (bins,
            # selections): the facts are the primary information.
            for i, child in enumerate(contentnode.children):
                if isinstance(child, nodes.table):
                    contentnode.insert(i, fl)
                    break
            else:
                contentnode += fl

    def _sig_names(self, names, sep):
        """Signature nodes for ``a × b`` / ``» a, b``: references to members."""
        out = []
        for i, n in enumerate(names):
            if i:
                out.append(addnodes.desc_sig_punctuation("", sep))
                out.append(addnodes.desc_sig_space())
            out.append(self._xref(n))
        return out


class PyRandClass(_VscObjectMixin, PyClasslike):
    """``.. py:randclass:: AluTxn(*, op: u4 = 0)``"""

    def get_signature_prefix(self, sig):
        prefix = list(super().get_signature_prefix(sig))
        return prefix[:-2] + _keyword("rand class")

    def get_index_text(self, modname, name_cls):
        if not modname:
            return _("%s (rand class)") % name_cls[0]
        return _("%s (rand class in %s)") % (name_cls[0], modname)


class PyCovergroup(_VscObjectMixin, PyClasslike):
    """``.. py:covergroup:: AluCov``"""

    def get_signature_prefix(self, sig):
        prefix = list(super().get_signature_prefix(sig))
        return prefix[:-2] + _keyword("covergroup")

    def get_index_text(self, modname, name_cls):
        if not modname:
            return _("%s (covergroup)") % name_cls[0]
        return _("%s (covergroup in %s)") % (name_cls[0], modname)


def _member_index_text(self, modname, name_cls, what):
    name, _cls = name_cls
    try:
        clsname, attr = name.rsplit(".", 1)
        if modname and self.config.add_module_names:
            clsname = "%s.%s" % (modname, clsname)
    except ValueError:
        return name
    return "%s (%s %s)" % (attr, clsname, what)


class PyRandField(_VscObjectMixin, PyAttribute):
    """``.. py:randfield:: op`` with ``:type: u4`` and ``:kind: rand``.

    ``:kind:`` is ``rand``, ``randc``, ``state``, ``cg_arg`` or
    ``sample_arg``; the other options become a list of facts."""

    option_spec = PyAttribute.option_spec.copy()
    option_spec.update({
        "kind": directives.unchanged,
        "domain": directives.unchanged,
        "size": directives.unchanged,
        "soft": directives.unchanged,
        "constrained-by": directives.unchanged,
        "inherited-from": directives.unchanged,
        "opaque": directives.flag,
    })

    _KIND_TEXT = {"state": "", "cg_arg": "cg_arg", "sample_arg": "sample_arg"}

    def get_signature_prefix(self, sig):
        kind = self.options.get("kind", "rand")
        text = self._KIND_TEXT.get(kind, kind)
        return _keyword(text) if text else []

    def get_index_text(self, modname, name_cls):
        return _member_index_text(self, modname, name_cls, _("field"))

    def _facts(self):
        o = self.options
        out = []
        if o.get("domain"):
            out.append((_("Domain"), o["domain"]))
        if o.get("size"):
            out.append((_("Size"), o["size"]))
        if o.get("soft"):
            out.append((_("Soft default"), o["soft"]))
        if "opaque" in o:
            out.append((_("Solver"), _("not visible to the solver (opaque state)")))
        if o.get("constrained-by"):
            out.append((_("Constrained by"), self._xref_list(_names(o["constrained-by"]))))
        if o.get("inherited-from"):
            para = nodes.paragraph()
            para += self._xref(o["inherited-from"], reftype="class")
            out.append((_("Inherited from"), para))
        return out


class PyConstraint(_VscObjectMixin, PyMethod):
    """``.. py:constraint:: c_op`` / ``.. py:constraint:: c_small(n=16)``.

    ``:kind:`` is ``fixed`` (default), ``generic``, ``value`` or ``dynamic``
    (classic). ``:reads:`` lists the fields read, ``:uses:`` the generics
    referenced, ``:used-by:`` the constraints referencing this one. With
    ``:signature-fields:`` the fields read also appear in the signature line,
    ``c_op » op, a, b``."""

    option_spec = PyMethod.option_spec.copy()
    option_spec.update({
        "kind": directives.unchanged,
        "reads": directives.unchanged,
        "uses": directives.unchanged,
        "used-by": directives.unchanged,
        "overrides": directives.unchanged,
        "inherited-from": directives.unchanged,
        "signature-fields": directives.flag,
    })

    _KIND_TEXT = {"fixed": "constraint", "generic": "generic constraint",
                  "value": "value constraint", "dynamic": "dynamic constraint"}

    def needs_arglist(self):
        return False

    def get_signature_prefix(self, sig):
        kind = self.options.get("kind", "fixed")
        return _keyword(self._KIND_TEXT.get(kind, kind + " constraint"))

    def handle_signature(self, sig, signode):
        ret = super().handle_signature(sig, signode)
        reads = _names(self.options.get("reads"))
        if "signature-fields" in self.options and reads:
            signode += addnodes.desc_sig_space()
            signode += addnodes.desc_sig_punctuation("", "»")
            signode += addnodes.desc_sig_space()
            for n in self._sig_names(reads, ","):
                signode += n
        return ret

    def get_index_text(self, modname, name_cls):
        return _member_index_text(self, modname, name_cls, _("constraint"))

    def _facts(self):
        o = self.options
        out = []
        if o.get("reads"):
            out.append((_("Reads"), self._xref_list(_names(o["reads"]))))
        if o.get("uses"):
            out.append((_("Uses"), self._xref_list(_names(o["uses"]))))
        if o.get("used-by"):
            out.append((_("Referenced by"), self._xref_list(_names(o["used-by"]))))
        if o.get("overrides"):
            para = nodes.paragraph()
            para += self._xref(o["overrides"])
            out.append((_("Overrides"), para))
        if o.get("inherited-from"):
            para = nodes.paragraph()
            para += self._xref(o["inherited-from"], reftype="class")
            out.append((_("Inherited from"), para))
        return out


class PyCoverpoint(_VscObjectMixin, PyAttribute):
    """``.. py:coverpoint:: mode`` with ``:type: u2``.

    ``:sampled:`` is the sampled expression of a pull coverpoint, or absent for
    a push coverpoint (``:formal:`` gives its position in ``sample()``)."""

    option_spec = PyAttribute.option_spec.copy()
    option_spec.update({
        "sampled": directives.unchanged,
        "formal": directives.unchanged,
        "iff": directives.unchanged,
        "bins": directives.unchanged,
        "crossed-by": directives.unchanged,
        "inherited-from": directives.unchanged,
    })

    def get_signature_prefix(self, sig):
        return _keyword("coverpoint")

    def get_index_text(self, modname, name_cls):
        return _member_index_text(self, modname, name_cls, _("coverpoint"))

    def _facts(self):
        o = self.options
        out = []
        if o.get("sampled"):
            out.append((_("Samples"), nodes.paragraph(
                "", "", nodes.literal(o["sampled"], o["sampled"]))))
        else:
            text = _("pushed: set with .set() or passed to sample()")
            if o.get("formal"):
                text = _("pushed: sample() formal %s, or .set()") % o["formal"]
            out.append((_("Samples"), text))
        if o.get("iff"):
            out.append((_("Guard"), nodes.paragraph(
                "", "", nodes.literal(o["iff"], "iff " + o["iff"]))))
        if o.get("bins"):
            out.append((_("Bins"), o["bins"]))
        if o.get("crossed-by"):
            out.append((_("Crossed by"), self._xref_list(_names(o["crossed-by"]))))
        if o.get("inherited-from"):
            para = nodes.paragraph()
            para += self._xref(o["inherited-from"], reftype="class")
            out.append((_("Inherited from"), para))
        return out


class PyCross(_VscObjectMixin, PyAttribute):
    """``.. py:cross:: op_x_mode`` with ``:components: op, mode``, shown as
    ``cross op_x_mode = op × mode``."""

    option_spec = PyAttribute.option_spec.copy()
    option_spec.update({
        "components": directives.unchanged,
        "bins": directives.unchanged,
        "crossed-by": directives.unchanged,
        "inherited-from": directives.unchanged,
    })

    def get_signature_prefix(self, sig):
        return _keyword("cross")

    def handle_signature(self, sig, signode):
        ret = super().handle_signature(sig, signode)
        comps = _names(self.options.get("components"))
        if comps:
            signode += addnodes.desc_sig_space()
            signode += addnodes.desc_sig_operator("", "=")
            signode += addnodes.desc_sig_space()
            for i, n in enumerate(comps):
                if i:
                    signode += addnodes.desc_sig_space()
                    signode += addnodes.desc_sig_operator("", "×")
                    signode += addnodes.desc_sig_space()
                signode += self._xref(n)
        return ret

    def get_index_text(self, modname, name_cls):
        return _member_index_text(self, modname, name_cls, _("cross"))

    def _facts(self):
        o = self.options
        out = []
        if o.get("bins"):
            out.append((_("Bins"), o["bins"]))
        if o.get("crossed-by"):
            out.append((_("Crossed by"), self._xref_list(_names(o["crossed-by"]))))
        if o.get("inherited-from"):
            para = nodes.paragraph()
            para += self._xref(o["inherited-from"], reftype="class")
            out.append((_("Inherited from"), para))
        return out


DIRECTIVES = {
    "randclass": PyRandClass,
    "covergroup": PyCovergroup,
    "randfield": PyRandField,
    "constraint": PyConstraint,
    "coverpoint": PyCoverpoint,
    "cross": PyCross,
}


def _add_stock_css_class(app, domain, objtype, contentnode):
    """``object-description-transform``: give our entries the stock CSS class
    of the Python object they are (``class``, ``attribute``, ``method``) beside
    their own, so themes style them."""
    if domain != "py" or objtype not in OBJECT_TYPES:
        return
    desc = contentnode.parent
    stock = OBJECT_TYPES[objtype][2]
    if desc is not None and stock not in desc["classes"]:
        desc["classes"].append(stock)


def setup_domain(app):
    """Register the object types, directives and roles on the ``py`` domain.

    There is no public API for adding an object type to an existing domain;
    ``registry.domain_object_types`` is what ``create_domains`` reads (the same
    approach as autodoc_pydantic and sphinx-toolbox)."""
    object_types = app.registry.domain_object_types.setdefault("py", {})
    for name, (label, roles, _css) in OBJECT_TYPES.items():
        object_types[name] = ObjType(label, *roles)
        app.add_directive_to_domain("py", name, DIRECTIVES[name])
        app.add_role_to_domain("py", name, PyXRefRole())
    app.connect("object-description-transform", _add_stock_css_class)
