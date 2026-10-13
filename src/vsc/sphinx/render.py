"""
Description objects -> reST lines.

The same lines are appended to a class docstring by the autodoc event handler
and parsed by the ``autorandclass`` / ``autocovergroup`` directives. They use
the ``py:randfield`` / ``py:constraint`` / ``py:coverpoint`` / ``py:cross``
directives (``domain.py``), nested in the class body so their full names are
``module.Class.member``.

See ``doc/notes/sphinx_extension_design.md`` §5.3 and §6.
"""


# Option defaults: the ``vsc_<name>`` config values / ``:<name>:`` directive
# options (with '_' for '-'). See design §8.
DEFAULTS = {
    "autodoc_enable": True,
    "randclass_hide_paramlist": False,
    "randclass_summary": "table",
    "randclass_member_groups": "fields, constraints, generics",
    "randclass_show_mode_hint": False,
    "field_show_constraints": True,
    "field_show_domain": True,
    "constraint_show_source": "body",
    "constraint_show_fields": True,
    "constraint_signature_fields": False,
    "constraint_show_refs": True,
    "covergroup_summary": "table",
    "coverpoint_show_bins": True,
    "coverpoint_show_options": True,
    "cross_show_selections": True,
    "type_style": "alias",
    "covergroup_elaborate": True,
    "classic_instantiate": False,
}

SUMMARY_CHOICES = ("table", "list", "none")
SOURCE_CHOICES = ("body", "collapsed", "none")
TYPE_STYLES = ("alias", "sv", "words")


class Options:
    """Resolved options: a directive override if given, else the config value."""

    def __init__(self, config=None, overrides=None):
        self._config = config
        self._overrides = overrides or {}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._overrides:
            return self._overrides[name]
        if self._config is not None:
            v = getattr(self._config, "vsc_" + name, None)
            if v is not None:
                return v
        return DEFAULTS[name]


def _bool(v):
    if isinstance(v, str):
        return v.strip().lower() not in ("", "0", "false", "no", "off")
    return bool(v)


def _list(v):
    if isinstance(v, str):
        return [s.strip() for s in v.split(",") if s.strip()]
    return list(v)


def _indent(lines, n=3):
    pad = " " * n
    return [pad + l if l else "" for l in lines]


def _lit(text):
    """An inline literal; backquote-safe."""
    text = " ".join(str(text).split())
    if "``" in text or text.endswith("`") or text.startswith("`"):
        return ":code:`%s`" % text.replace("`", "\\`")
    return "``%s``" % text


def _esc(text):
    """Escape inline markup characters in plain table/paragraph text."""
    out = str(text)
    for ch in ("\\", "*", "`", "|", "_"):
        out = out.replace(ch, "\\" + ch)
    return out


def _qual(t):
    return "%s.%s" % (t.__module__, t.__qualname__)


def _cls_target(t):
    return "%s <%s>" % (t.__qualname__, _qual(t))


def type_text(t, style):
    """Render a type string per ``vsc_type_style``: ``u4`` (alias),
    ``bit [3:0]`` (sv) or ``4-bit unsigned`` (words). Non-width types pass
    through."""
    import re
    m = re.fullmatch(r"([us])(\d+)((?:\[\d*\])?)", t)
    if not m or style == "alias":
        return t
    signed, bits, arr = m.group(1) == "s", int(m.group(2)), m.group(3)
    if style == "sv":
        base = "bit signed [%d:0]" % (bits - 1) if signed else "bit [%d:0]" % (bits - 1)
        return base + (" " + arr if arr else "")
    words = "%d-bit %s" % (bits, "signed" if signed else "unsigned")
    if arr:
        words = ("array[%s] of " % arr[1:-1] if arr != "[]" else "list of ") + words
    return words


class _Ctx:
    """Per-class rendering context: which members are rendered here (local
    names resolve), and where the rest live (full targets)."""

    def __init__(self, cls, rendered, owners):
        self.cls = cls
        self.rendered = set(rendered)
        self.owners = owners      # name -> owner class

    def target(self, name):
        """A name for a directive option / role: local if rendered here,
        ``name <module.Owner.name>`` if documented on a base class, else
        ``!name`` (Sphinx's "show, do not link")."""
        head = name.split(".")[0]
        if head in self.rendered:
            return name if name == head else "%s <%s>" % (name, head)
        if head in self.owners and self.owners[head] is not self.cls:
            return "%s <%s.%s>" % (name, _qual(self.owners[head]), head)
        return "!" + name

    def role(self, name):
        t = self.target(name)
        return ":py:obj:`%s`" % t


def _rendered(cls, members, inherited):
    return [m for m in members if inherited or m.owner is cls]


def _select(members, only, exclude):
    """Apply ``:members: a, b`` (``only``) and ``:exclude-members:``."""
    return tuple(m for m in members
                 if (only is None or m.name in only) and m.name not in exclude)


def _attr_doc(attr_doc, owner, name):
    if attr_doc is None:
        return []
    return list(attr_doc(owner, name) or [])


# --- Rand classes -----------------------------------------------------------


def render_randclass(desc, opts, attr_doc=None, inherited=False, only=None,
                     exclude=()):
    """reST lines for the body of a rand class, after its docstring. ``only``
    / ``exclude`` restrict the members shown (``:members: a, b`` /
    ``:exclude-members:``)."""
    import dataclasses
    desc = dataclasses.replace(
        desc, fields=_select(desc.fields, only, exclude),
        constraints=_select(desc.constraints, only, exclude),
        generics=_select(desc.generics, only, exclude))
    cls = desc.cls
    fields = _rendered(cls, desc.fields, inherited)
    constraints = _rendered(cls, desc.constraints, inherited)
    generics = _rendered(cls, desc.generics, inherited)
    owners = {m.name: m.owner for m in desc.fields + desc.constraints + desc.generics}
    ctx = _Ctx(cls, [m.name for m in fields + constraints + generics], owners)

    out = []
    summary = opts.randclass_summary
    if summary == "table":
        out += _fields_table(desc.fields, opts, ctx)
        out += _constraints_list(desc.constraints + desc.generics, ctx)
    elif summary == "list":
        out += _fields_list(desc.fields, opts, ctx)
        out += _constraints_list(desc.constraints + desc.generics, ctx)

    if _bool(opts.randclass_show_mode_hint) and (desc.fields or desc.constraints):
        out += ["Fields and constraints can be switched off per instance with "
                "``set_rand_mode(name, enabled)`` and "
                "``set_constraint_mode(name, enabled)``.", ""]

    groups = {
        "fields": ("Fields", [l for f in fields for l in
                              _field_entry(f, opts, ctx, attr_doc)]),
        "constraints": ("Constraints", [l for c in constraints for l in
                                        _constraint_entry(c, opts, ctx)]),
        "generics": ("Generic constraints", [l for c in generics for l in
                                             _constraint_entry(c, opts, ctx)]),
    }
    for g in _list(opts.randclass_member_groups):
        if g not in groups:
            continue
        title, lines = groups.pop(g)
        if lines:
            out += [".. rubric:: %s" % title, ""] + lines
    return out


def _fields_table(fields, opts, ctx):
    if not fields:
        return []
    style = opts.type_style
    show_dom = _bool(opts.field_show_domain) and any(f.domain or f.size for f in fields)
    show_cons = _bool(opts.field_show_constraints) and any(f.constrained_by for f in fields)
    head = ["Field", "Type", "Kind"]
    if show_dom:
        head.append("Domain / size")
    if show_cons:
        head.append("Constrained by")
    rows = []
    for f in fields:
        row = [ctx.role(f.name), _esc(type_text(f.type_str, style)) or " ",
               _esc(_kind_text(f))]
        if show_dom:
            row.append(_esc("; ".join(x for x in (f.domain, f.size) if x)) or " ")
        if show_cons:
            row.append(", ".join(ctx.role(c) for c in f.constrained_by) or " ")
        rows.append(row)
    return _list_table("Fields", head, rows)


def _fields_list(fields, opts, ctx):
    if not fields:
        return []
    out = []
    for f in fields:
        out.append("* %s: %s, %s" % (ctx.role(f.name),
                                     _esc(type_text(f.type_str, opts.type_style)),
                                     _esc(_kind_text(f))))
    return [".. rubric:: Fields", ""] + out + [""]


def _constraints_list(cons, ctx):
    if not cons:
        return []
    rows = []
    for c in cons:
        first = (c.doc or "").strip().split("\n\n")[0].replace("\n", " ")
        rows.append([ctx.role(c.name), _esc(c.kind), first or " "])
    return _list_table("Constraints", ["Constraint", "Kind", "Description"], rows)


def _kind_text(f):
    if f.opaque:
        return "state (opaque)"
    return f.kind


def _list_table(title, head, rows):
    out = [".. list-table:: %s" % title, "   :header-rows: 1", ""]
    for r in [head] + rows:
        for i, cell in enumerate(r):
            out.append(("   * - " if i == 0 else "     - ") + (cell or " "))
    out.append("")
    return out


def _field_entry(f, opts, ctx, attr_doc):
    out = [".. py:randfield:: %s" % f.name,
           "   :kind: %s" % f.kind]
    if f.type_str:
        out.append("   :type: %s" % type_text(f.type_str, opts.type_style))
    if f.default not in (None, "0"):
        out.append("   :value: %s" % f.default)
    if _bool(opts.field_show_domain):
        if f.domain:
            out.append("   :domain: %s" % f.domain)
        if f.size:
            out.append("   :size: %s" % f.size)
    if f.soft is not None:
        out.append("   :soft: %s" % f.soft)
    if f.opaque:
        out.append("   :opaque:")
    if _bool(opts.field_show_constraints) and f.constrained_by:
        out.append("   :constrained-by: %s" % ", ".join(
            ctx.target(c) for c in f.constrained_by))
    if f.owner is not ctx.cls:
        out.append("   :inherited-from: %s" % _cls_target(f.owner))
    out.append("")
    doc = _attr_doc(attr_doc, f.owner, f.name)
    if doc:
        out += _indent(doc) + [""]
    return out


def _constraint_entry(c, opts, ctx):
    out = [".. py:constraint:: %s%s" % (c.name, c.signature),
           "   :kind: %s" % c.kind]
    if c.fields_read and (_bool(opts.constraint_show_fields)
                          or _bool(opts.constraint_signature_fields)):
        out.append("   :reads: %s" % ", ".join(ctx.target(n) for n in c.fields_read))
        if _bool(opts.constraint_signature_fields):
            out.append("   :signature-fields:")
    if _bool(opts.constraint_show_refs):
        if c.generics_used:
            out.append("   :uses: %s" % ", ".join(ctx.target(n) for n in c.generics_used))
        if c.used_by:
            out.append("   :used-by: %s" % ", ".join(ctx.target(n) for n in c.used_by))
    if c.overrides is not None:
        out.append("   :overrides: %s <%s.%s>" % (
            "%s.%s" % (c.overrides.__qualname__, c.name), _qual(c.overrides), c.name))
    if c.owner is not ctx.cls:
        out.append("   :inherited-from: %s" % _cls_target(c.owner))
    out.append("")
    body = []
    if c.doc:
        body += c.doc.splitlines() + [""]
    body += _source_block(c.source, opts.constraint_show_source)
    out += _indent(body)
    return out


def _source_block(source, mode):
    if not source or mode == "none":
        return []
    block = [".. code-block:: python", ""] + _indent(source.splitlines()) + [""]
    if mode == "collapsed":
        return ([".. raw:: html", "", "   <details><summary>Source</summary>", ""]
                + block
                + [".. raw:: html", "", "   </details>", ""])
    return block


# --- Covergroups ------------------------------------------------------------


def render_covergroup(desc, opts, attr_doc=None, inherited=False, only=None,
                      exclude=()):
    """reST lines for the body of a covergroup, after its docstring."""
    import dataclasses
    desc = dataclasses.replace(
        desc, fields=_select(desc.fields, only, exclude),
        coverpoints=_select(desc.coverpoints, only, exclude),
        crosses=_select(desc.crosses, only, exclude),
        sample=None if (desc.sample is None or "sample" in exclude
                        or (only is not None and "sample" not in only))
        else desc.sample)
    cls = desc.cls
    fields = _rendered(cls, desc.fields, inherited)
    cps = _rendered(cls, desc.coverpoints, inherited)
    crs = _rendered(cls, desc.crosses, inherited)
    owners = {m.name: m.owner for m in desc.fields + desc.coverpoints + desc.crosses}
    ctx = _Ctx(cls, [m.name for m in fields + cps + crs] + ["sample"], owners)
    style = opts.type_style

    out = []
    if desc.sample is not None:
        params = ", ".join("%s: %s" % (n, t) for n, t, _r in desc.sample)
        out += [".. py:method:: sample(%s)" % params, ""]
        if desc.sample and desc.classic:
            out += _indent([
                "Sample the covergroup: pass a value for each sampling input, "
                "in order; every coverpoint and cross is then binned.", ""])
        elif desc.sample:
            out += _indent([
                "Sample the covergroup. Each argument sets the coverpoint or "
                "sampling input of the same name (positional in declaration "
                "order, or by keyword); an omitted argument keeps its previous "
                "value.", ""])
        else:
            out += _indent(["Sample the covergroup: re-bin the current state.", ""])

    summary = opts.covergroup_summary
    if summary in ("table", "list") and (desc.coverpoints or desc.crosses):
        out += _cg_summary(desc, ctx, style, summary)

    if fields:
        out += [".. rubric:: Sampling inputs", ""]
        for f in fields:
            out += _field_entry(f, opts, ctx, attr_doc)
    if cps:
        out += [".. rubric:: Coverpoints", ""]
        for cp in cps:
            out += _coverpoint_entry(cp, opts, ctx, attr_doc)
    if crs:
        out += [".. rubric:: Crosses", ""]
        for x in crs:
            out += _cross_entry(x, opts, ctx, attr_doc)
    return out


def _bin_count(cp):
    if cp.n_bins is not None:
        return str(cp.n_bins)
    if not cp.bins:
        return cp.auto_bins and "auto"
    counts = [b.count for b in cp.bins]
    if any(c is None for c in counts):
        return None
    return str(sum(counts))


def _cg_summary(desc, ctx, style, summary):
    out = []
    if summary == "list":
        items = ["* %s: %s, %s" % (ctx.role(cp.name), _esc(type_text(cp.type_str, style)),
                                   "push" if cp.push else "pull")
                 for cp in desc.coverpoints]
        items += ["* %s: %s" % (ctx.role(x.name), " × ".join(ctx.role(c) for c in x.components))
                  for x in desc.crosses]
        return [".. rubric:: Summary", ""] + items + [""]
    if desc.coverpoints:
        rows = [[ctx.role(cp.name), _esc(type_text(cp.type_str, style)),
                 "push" if cp.push else "pull", _bin_count(cp) or " "]
                for cp in desc.coverpoints]
        out += _list_table("Coverpoints", ["Coverpoint", "Type", "Sampling", "Bins"], rows)
    if desc.crosses:
        counted = any(x.n_bins is not None for x in desc.crosses)
        rows = [[ctx.role(x.name), " × ".join(ctx.role(c) for c in x.components)]
                + ([cross_bins_text(x) or " "] if counted else [])
                for x in desc.crosses]
        out += _list_table("Crosses", ["Cross", "Components"]
                           + (["Bins"] if counted else []), rows)
    return out


def cross_bins_text(x):
    """``18: 13 counted, 5 ignored`` for an elaborated cross, else None."""
    if x.n_bins is None:
        return None
    excluded = [(x.n_ignore or 0, "ignored"), (x.n_illegal or 0, "illegal")]
    excluded = ["%d %s" % (n, what) for n, what in excluded if n]
    if not excluded:
        return str(x.n_bins)
    counted = x.n_bins - (x.n_ignore or 0) - (x.n_illegal or 0)
    return "%d: %s" % (x.n_bins, ", ".join(["%d counted" % counted] + excluded))


def _coverpoint_entry(cp, opts, ctx, attr_doc):
    out = [".. py:coverpoint:: %s" % cp.name,
           "   :type: %s" % type_text(cp.type_str, opts.type_style)]
    if not cp.push:
        out.append("   :sampled: %s" % (cp.ref_src or "(pull)"))
    elif cp.sample_index is not None:
        out.append("   :formal: %d" % (cp.sample_index + 1))
    if cp.iff_src:
        out.append("   :iff: %s" % cp.iff_src)
    if _bool(opts.coverpoint_show_bins):
        if cp.auto_bins:
            out.append("   :bins: automatic, %s" % cp.auto_bins)
        elif cp.n_bins is not None:
            out.append("   :bins: %d" % cp.n_bins)
    if cp.crossed_by:
        out.append("   :crossed-by: %s" % ", ".join(ctx.target(n) for n in cp.crossed_by))
    if cp.owner is not ctx.cls:
        out.append("   :inherited-from: %s" % _cls_target(cp.owner))
    out.append("")
    body = _attr_doc(attr_doc, cp.owner, cp.name)
    if body:
        body.append("")
    if _bool(opts.coverpoint_show_bins):
        body += _bins_table("Bins", cp.bins)
        body += _bins_table("Ignore bins", cp.ignore)
        body += _bins_table("Illegal bins", cp.illegal)
    if _bool(opts.coverpoint_show_options) and cp.options:
        body += ["Options: %s" % ", ".join(_lit("%s=%r" % kv) for kv in cp.options), ""]
    return out + _indent(body)


def _bins_table(title, bins):
    if not bins:
        return []
    with_doc = any(b.doc for b in bins)
    head = ["Bin", "Kind", "Values", "Count"] + (["Description"] if with_doc else [])
    rows = []
    for b in bins:
        if b.count is None:
            count = "per value"
        elif b.count == 0:
            count = "0 (all values excluded)"
        else:
            count = str(b.count)
        r = [_lit(b.name), _esc(b.kind), _lit(b.values) if b.values else " ",
             count]
        if with_doc:
            r.append(_esc(b.doc) if b.doc else " ")
        rows.append(r)
    return _list_table(title, head, rows)


def _cross_entry(x, opts, ctx, attr_doc):
    out = [".. py:cross:: %s" % x.name]
    if x.components:
        out.append("   :components: %s" % ", ".join(ctx.target(c) for c in x.components))
    if x.n_bins is not None:
        out.append("   :bins: %s" % cross_bins_text(x))
    if x.crossed_by:
        out.append("   :crossed-by: %s" % ", ".join(ctx.target(n) for n in x.crossed_by))
    if x.owner is not ctx.cls:
        out.append("   :inherited-from: %s" % _cls_target(x.owner))
    out.append("")
    body = _attr_doc(attr_doc, x.owner, x.name)
    if body:
        body.append("")
    if _bool(opts.cross_show_selections):
        body += _sel_table("Ignore bins", x.ignore)
        body += _sel_table("Illegal bins", x.illegal)
    if _bool(opts.coverpoint_show_options) and x.options:
        body += ["Options: %s" % ", ".join(_lit("%s=%r" % kv) for kv in x.options), ""]
    return out + _indent(body)


def _sel_table(title, sels):
    if not sels:
        return []
    with_doc = any(s.doc for s in sels)
    head = ["Name", "Selection"] + (["Description"] if with_doc else [])
    rows = []
    for s in sels:
        r = [_lit(s.name), _lit(s.expr)]
        if with_doc:
            r.append(_esc(s.doc) if s.doc else " ")
        rows.append(r)
    return _list_table(title, head, rows)
