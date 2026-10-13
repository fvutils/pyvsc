"""
``autorandclass`` / ``autocovergroup``: ``autoclass`` with per-class pyvsc
options.

The event handlers (``events.py``) can only read ``conf.py``. These
directives accept every ``vsc_<object>_<option>`` as ``:<object>-<option>:``,
make them visible to the handlers for the duration of the run, and delegate
everything else to whatever ``autoclass`` directive is registered, so the
output is the same as ``autoclass`` produces, on every Sphinx version.

See ``doc/notes/sphinx_extension_design.md`` §5.3 and §8.
"""
from docutils.parsers.rst import directives as _rst_directives
from sphinx.util import logging
from sphinx.util.docutils import SphinxDirective

from . import introspect as I
from . import render as R

logger = logging.getLogger(__name__)


def _choice(choices):
    def conv(arg):
        return _rst_directives.choice(arg, choices)
    return conv


def _flag_or_bool(arg):
    """``:opt:`` alone means true; ``:opt: false`` / ``no`` / ``0`` false."""
    if arg is None or not arg.strip():
        return True
    return R._bool(arg)


# Directive option -> (render option name, converter).
VSC_OPTIONS = {}
for _name, _default in R.DEFAULTS.items():
    if _name == "autodoc_enable":
        continue
    if isinstance(_default, bool):
        _conv = _flag_or_bool
    elif _name.endswith("_summary"):
        _conv = _choice(R.SUMMARY_CHOICES)
    elif _name == "constraint_show_source":
        _conv = _choice(R.SOURCE_CHOICES)
    elif _name == "type_style":
        _conv = _choice(R.TYPE_STYLES)
    else:
        _conv = _rst_directives.unchanged
    VSC_OPTIONS[_name.replace("_", "-")] = (_name, _conv)
del _name, _default, _conv


class _AnyOptions(dict):
    """Accept any option at parse time; split and validate in ``run``."""

    def __bool__(self):
        return True

    def __contains__(self, key):
        return True

    def __getitem__(self, key):
        return lambda arg: arg


class _AutoVscClass(SphinxDirective):
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    has_content = True
    option_spec = _AnyOptions()

    expected = None         # predicate on the imported class
    what = ""

    def run(self):
        overrides = {}
        passthrough = {}
        for k, v in self.options.items():
            if k in VSC_OPTIONS:
                name, conv = VSC_OPTIONS[k]
                try:
                    overrides[name] = conv(v)
                except ValueError as e:
                    logger.warning("%s: option %r: %s", self.name, k, e,
                                   location=self.get_location())
            else:
                passthrough[k] = v

        autoclass = _rst_directives._directives.get("autoclass")
        if autoclass is None:
            logger.warning("%s needs sphinx.ext.autodoc in extensions", self.name,
                           location=self.get_location())
            return []

        stack = self.env.temp_data.setdefault("vsc_overrides", [])
        stack.append(overrides)
        try:
            delegate = autoclass("autoclass", self.arguments, passthrough,
                                 self.content, self.lineno, self.content_offset,
                                 self.block_text, self.state, self.state_machine)
            result = delegate.run()
        finally:
            stack.pop()
            if not stack:
                self.env.temp_data.pop("vsc_overrides", None)

        self._check_kind()
        return result

    def _check_kind(self):
        from .events import _resolve
        name = self.arguments[0].strip()
        modname = self.env.ref_context.get("py:module")
        obj = _resolve(name)
        if obj is None and modname:
            obj = _resolve("%s.%s" % (modname, name))
        if obj is not None and not type(self).expected(obj):
            logger.warning("%s: %s is not a %s; documented as a plain class",
                           self.name, name, self.what,
                           location=self.get_location())


class AutoRandClass(_AutoVscClass):
    """``.. autorandclass:: pkg.AluTxn`` with any ``autoclass`` option plus
    the ``:randclass-*:`` / ``:field-*:`` / ``:constraint-*:`` options."""
    expected = staticmethod(lambda o: I.is_randclass(o) or I.is_classic_randobj(o))
    what = "rand class"


class AutoCovergroup(_AutoVscClass):
    """``.. autocovergroup:: pkg.AluCov`` with any ``autoclass`` option plus
    the ``:covergroup-*:`` / ``:coverpoint-*:`` / ``:cross-*:`` options."""
    expected = staticmethod(lambda o: I.is_covergroup(o) or I.is_classic_covergroup(o))
    what = "covergroup"
