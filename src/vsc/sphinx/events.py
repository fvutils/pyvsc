"""
autodoc event handlers: pyvsc-aware output from plain ``automodule`` /
``autoclass``, on every Sphinx version (7, 8, and 9's rewritten autodoc).

- ``autodoc-process-docstring``: append the generated fields / constraints /
  coverpoints / crosses to a pyvsc class's docstring.
- ``autodoc-skip-member``: drop what we rendered, and pyvsc's own machinery,
  so autodoc does not document it again.
- ``autodoc-process-signature``: ``Annotated[int, _Width(4, unsigned)]`` ->
  ``u4``; optional parameter-list hiding; classic signature recovery.
- ``doctree-read``: give a documented pyvsc class the ``randclass`` /
  ``covergroup`` object type in place of ``class``.

See ``doc/notes/sphinx_extension_design.md`` §5.3.
"""
import functools
import inspect
import re
import sys

from docutils import nodes
from sphinx import addnodes
from sphinx.errors import PycodeError
from sphinx.pycode import ModuleAnalyzer

from sphinx.util import logging

from . import elaborate as E
from . import introspect as I
from . import render as R

logger = logging.getLogger(__name__)


# --- Shared -----------------------------------------------------------------


@functools.lru_cache(maxsize=None)
def _describe(cls, elaborate, instantiate):
    """(description or None, ElaborationError or None). Cached: a class's
    structure is fixed once it is decorated. When elaboration fails, the
    static description is returned with the error."""
    try:
        if I.is_randclass(cls):
            return I.describe_randclass(cls), None
        if I.is_covergroup(cls):
            if elaborate:
                return E.elaborate_covergroup(cls), None
            return I.describe_covergroup(cls), None
        if I.is_classic_randobj(cls):
            if instantiate:
                return E.instantiate_classic_randobj(cls), None
            return I.describe_classic_randobj(cls), None
        if I.is_classic_covergroup(cls):
            if instantiate:
                return E.instantiate_classic_covergroup(cls), None
            return I.describe_classic_covergroup(cls), None
    except E.ElaborationError as e:
        return _describe(cls, False, False)[0], e
    return None, None


def describe(cls, elaborate=False, instantiate=False):
    """The description of a pyvsc class, or None."""
    return _describe(cls, elaborate, instantiate)[0]


def describe_for(app, cls):
    """The description of ``cls`` with the elaboration options in effect for
    the object being documented. A failed elaboration is reported once per
    build (``suppress_warnings = ["vsc.elaborate"]`` silences it)."""
    opts = current_options(app)
    key = (cls, R._bool(opts.covergroup_elaborate),
           R._bool(opts.classic_instantiate))
    desc, err = _describe(*key)
    if err is not None:
        warned = app.__dict__.setdefault("_vsc_elaborate_warned", set())
        if key not in warned:
            warned.add(key)
            logger.warning("%s; documented without it", err, type="vsc",
                           subtype="elaborate",
                           location=app.env.docname if app.env else None)
    return desc


def attr_doc(owner, name):
    """The ``#:`` comment / docstring-after-assignment for a class attribute,
    from Sphinx's source analyzer (the convention autodoc uses)."""
    try:
        analyzer = ModuleAnalyzer.for_module(owner.__module__)
        docs = analyzer.find_attr_docs()
    except PycodeError:
        return []
    lines = list(docs.get((owner.__qualname__, name), []))
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def current_options(app):
    """Options for the object being documented: the innermost
    ``autorandclass`` / ``autocovergroup`` overrides, else ``conf.py``."""
    stack = app.env.temp_data.get("vsc_overrides") if app.env else None
    return R.Options(app.config, stack[-1] if stack else None)


def render_lines(desc, opts, inherited=False, only=None, exclude=()):
    if isinstance(desc, I.CovergroupDesc):
        return R.render_covergroup(desc, opts, attr_doc, inherited, only, exclude)
    return R.render_randclass(desc, opts, attr_doc, inherited, only, exclude)


def _enabled(app):
    return bool(app.config.vsc_autodoc_enable) or \
        bool(app.env and app.env.temp_data.get("vsc_overrides"))


def _option(options, name):
    """Read an autodoc option on Sphinx 7-9 (an ``Options`` dict with
    attribute access, or the Sphinx 9 options object)."""
    try:
        return getattr(options, name, None)
    except Exception:
        return None


# --- autodoc-process-docstring ----------------------------------------------


class _Last:
    """The previous ``autodoc-process-docstring`` call. With
    ``autoclass_content = "both"`` the class and ``__init__`` docstrings
    arrive as two consecutive calls for the same class; we append once."""
    key = None


def reset_docstring_state(app, docname, source):
    """``source-read``: a new document starts; forget the previous call."""
    _Last.key = None


def process_docstring(app, what, name, obj, options, lines):
    key = (app.env.docname if app.env else None, what, name)
    first = _Last.key != key
    _Last.key = key
    if not _enabled(app):
        return

    if what in ("class", "exception"):
        desc = describe_for(app, obj) if isinstance(obj, type) else None
        if desc is None or not first:
            return
        _strip_dataclass_doc(obj, lines)
        opts = current_options(app)
        inherited = bool(_option(options, "inherited_members"))
        # ``:members: a, b`` restricts the pyvsc members too. Without
        # ``:members:``, Sphinx <= 8 passes [] and 9 passes None: no restriction.
        members = _option(options, "members")
        only = set(members) if isinstance(members, (list, tuple)) and members \
            else None
        exclude = set(_option(options, "exclude_members") or ())
        generated = render_lines(desc, opts, inherited, only, exclude)
        if generated:
            if lines and lines[-1].strip():
                lines.append("")
            lines.extend(generated)
    elif what == "attribute":
        _attribute_doc(app, name, lines)


def _strip_dataclass_doc(cls, lines):
    """``dataclasses`` gives an undocumented class the docstring
    ``AluTxn(*, op: Annotated[...] = 0)``; drop it."""
    doc = cls.__dict__.get("__doc__") or ""
    if doc.startswith(cls.__name__ + "(") and "\n" not in doc.strip():
        text = " ".join(l.strip() for l in lines if l.strip())
        if text == doc.strip():
            del lines[:]


def _attribute_doc(app, name, lines):
    """``autoattribute AluTxn.op`` written by hand: add the field facts."""
    parent_name, _, attr = name.rpartition(".")
    parent = _resolve(parent_name)
    desc = describe_for(app, parent) if isinstance(parent, type) else None
    if desc is None:
        return
    facts = []
    for f in desc.fields:
        if f.name == attr:
            facts = [(":Kind:", f.kind), (":Type:", f.type_str),
                     (":Domain:", f.domain), (":Size:", f.size),
                     (":Constrained by:", ", ".join(f.constrained_by))]
    for cp in getattr(desc, "coverpoints", ()):
        if cp.name == attr:
            facts = [(":Coverpoint:", cp.type_str),
                     (":Samples:", cp.ref_src or "pushed")]
    for x in getattr(desc, "crosses", ()):
        if x.name == attr:
            facts = [(":Cross:", " x ".join(x.components))]
    facts = [(k, v) for k, v in facts if v]
    if facts:
        if lines and lines[-1].strip():
            lines.append("")
        lines.extend("%s %s" % kv for kv in facts)


def _resolve(dotted):
    """The object at ``pkg.mod.Class`` (already imported by autodoc)."""
    parts = dotted.split(".")
    for i in range(len(parts), 0, -1):
        mod = sys.modules.get(".".join(parts[:i]))
        if mod is None:
            continue
        obj = mod
        try:
            for p in parts[i:]:
                obj = getattr(obj, p)
        except AttributeError:
            return None
        return obj
    return None


# --- autodoc-skip-member ----------------------------------------------------


def _machinery_owner(cls, name):
    """The class in ``cls``'s MRO that defines ``name``."""
    for k in cls.__mro__:
        if name in k.__dict__:
            return k
    return None


def _parent_class():
    """The class whose members autodoc is filtering. The event does not pass
    it, so read it from the autodoc frame that is filtering: ``props`` (Sphinx
    9) or the documenter ``self`` (Sphinx <= 8, and 9's legacy mode)."""
    f = sys._getframe(2)
    while f is not None:
        if f.f_globals.get("__name__", "").startswith("sphinx.ext.autodoc"):
            loc = f.f_locals
            props = loc.get("props")
            obj = getattr(props, "_obj", None)
            if isinstance(obj, type):
                return obj
            doc = loc.get("self")
            if doc is not None and hasattr(doc, "filter_members"):
                obj = getattr(doc, "object", None)
                if isinstance(obj, type):
                    return obj
        f = f.f_back
    return None


def skip_member(app, what, name, obj, skip, options):
    if what not in ("class", "exception"):
        return None
    parent = _parent_class()
    if parent is None:
        return None
    desc = describe_for(app, parent)
    if desc is None:
        return None
    if name in desc.member_names():
        return True
    if getattr(desc, "classic", False):
        from vsc.constraints import constraint_t, dynamic_constraint_t
        if isinstance(obj, (constraint_t, dynamic_constraint_t)):
            return True
        owner = _machinery_owner(parent, name)
        if owner is not None and (owner.__module__.startswith("vsc.")
                                  or owner.__name__.endswith("_interposer")):
            return True
        if getattr(obj, "__module__", "").startswith("vsc."):
            return True
        return None
    owner = _machinery_owner(parent, name)
    if owner in (I.RandClass, I.Covergroup):
        return True
    if name in ("_vsc_type_model", "_vsc_cg_type_model"):
        return True
    return None


# --- autodoc-process-signature ----------------------------------------------


_ANNOTATED = re.compile(
    r"(?:~?typing\.)?Annotated\[int, _Width\((-?\d+), (signed|unsigned)\)\]")


def width_aliases(text):
    """``Annotated[int, _Width(4, unsigned)]`` -> ``u4`` (``bitv`` for the
    runtime-width alias)."""
    def sub(m):
        bits = int(m.group(1))
        if bits < 0:
            return "bitv"
        return "%s%d" % ("s" if m.group(2) == "signed" else "u", bits)
    return _ANNOTATED.sub(sub, text) if text else text


def process_signature(app, what, name, obj, options, signature, return_annotation):
    new_sig, new_ret = signature, return_annotation
    if what in ("class", "exception") and isinstance(obj, type):
        user = I.classic_user_class(obj)
        if user is not None:
            new_sig = _classic_signature(user)
        elif _enabled(app) and describe(obj) is not None and \
                R._bool(current_options(app).randclass_hide_paramlist):
            new_sig = ""
    new_sig = width_aliases(new_sig)
    new_ret = width_aliases(new_ret)
    if (new_sig, new_ret) != (signature, return_annotation):
        return new_sig, new_ret
    return None


def _classic_signature(user):
    """The user's ``__init__`` signature, not the interposer's
    ``(*args, **kwargs)``."""
    init = user.__dict__.get("__init__")
    if init is None:
        for k in user.__mro__[1:]:
            if k is object or k.__module__.startswith("vsc."):
                break
            init = k.__dict__.get("__init__")
            if init is not None:
                break
    if init is None:
        return "()"
    try:
        sig = inspect.signature(init)
    except (TypeError, ValueError):
        return None
    params = list(sig.parameters.values())[1:]
    return str(sig.replace(parameters=params, return_annotation=sig.empty))


# --- doctree-read -----------------------------------------------------------


_CLASS_TYPES = {"randclass": "rand class", "covergroup": "covergroup"}


def retype_classes(app, doctree):
    """autodoc writes ``.. py:class::`` for every class. For a pyvsc class,
    make the entry a ``randclass`` / ``covergroup``: object type (domain
    record, so inventories and ``:py:randclass:`` see it), CSS classes,
    signature prefix and index text."""
    if not _enabled(app):
        return
    domain = app.env.get_domain("py")
    for desc in list(doctree.findall(addnodes.desc)):
        if desc.get("domain") != "py" or desc.get("objtype") != "class":
            continue
        if not desc.children or not isinstance(desc[0], addnodes.desc_signature):
            continue
        sig = desc[0]
        fullname = sig.get("fullname")
        module = sig.get("module")
        if not fullname:
            continue
        obj = _resolve("%s.%s" % (module, fullname) if module else fullname)
        if I.is_randclass(obj) or I.is_classic_randobj(obj):
            new = "randclass"
        elif I.is_covergroup(obj) or I.is_classic_covergroup(obj):
            new = "covergroup"
        else:
            continue
        desc["objtype"] = desc["desctype"] = new
        desc["classes"].append(new)
        _retitle_prefix(sig, _CLASS_TYPES[new])
        full = "%s.%s" % (module, fullname) if module else fullname
        entry = domain.objects.get(full)
        if entry is not None and entry.objtype == "class":
            domain.objects[full] = entry._replace(objtype=new)
        _retitle_index(desc, "class", _CLASS_TYPES[new])


def _retitle_prefix(sig, text):
    for ann in sig.findall(addnodes.desc_annotation):
        for kw in list(ann.findall(addnodes.desc_sig_keyword)):
            if kw.astext() == "class":
                kw.parent.replace(kw, addnodes.desc_sig_keyword("", text))
                return
        for t in list(ann.findall(nodes.Text)):
            if t.astext() == "class":
                t.parent.replace(t, nodes.Text(text))
                return


def _retitle_index(desc, old, new):
    parent = desc.parent
    if parent is None:
        return
    i = parent.index(desc)
    if i == 0 or not isinstance(parent[i - 1], addnodes.index):
        return
    idx = parent[i - 1]
    entries = []
    for e in idx["entries"]:
        text = e[1].replace("(%s in " % old, "(%s in " % new) \
                   .replace("(built-in %s)" % old, "(%s)" % new)
        entries.append((e[0], text) + tuple(e[2:]))
    idx["entries"] = entries


# --- missing-reference ------------------------------------------------------


_WIDTH_TYPE = re.compile(
    r"(?:[us]\d+|bitv)(?:\[\d*\])?"                  # alias: u4, u8[4]
    r"|bit(?: signed)? \[\d+:0\](?: \[\d*\])?"       # sv: bit [3:0]
    r"|(?:array\[\d+\] of |list of )?\d+-bit (?:un)?signed")   # words


def width_type_reference(app, env, node, contnode):
    """``u4`` / ``s16`` / ``bitv`` in a type position are pyvsc width aliases
    (``bit [3:0]`` / ``4-bit unsigned`` in the other ``vsc_type_style``
    spellings), not classes to link: show them as text, without a nitpicky
    warning."""
    if node.get("refdomain") == "py" and \
            _WIDTH_TYPE.fullmatch(node.get("reftarget", "")):
        return contnode
    return None
