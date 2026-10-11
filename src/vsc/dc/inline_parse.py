"""
Parsed ``randomize_with`` bodies.

``with obj.randomize_with() as it:`` bodies follow the ``@vdc.constraint``
grammar: the body is parsed from source, never executed. This module finds the
body from the caller's frame (``locate``); see
``doc/notes/vdc_constraint_python_grammar.md`` §7 for the design.

:mod:`vsc.dc.inline` keeps the operator-overloading path, used when the source
cannot be read.
"""
import ast
import dis
import linecache

# Opcodes that call __enter__ for a ``with`` item.
_WITH_OPS = frozenset(("BEFORE_WITH", "SETUP_WITH"))


class Located:
    """The ``with`` statement of one call site, and the item that is ours."""
    __slots__ = ("node", "item", "it_name", "filename")

    def __init__(self, node, item, it_name, filename):
        self.node = node              # ast.With
        self.item = item              # ast.withitem
        self.it_name = it_name        # the ``as`` name
        self.filename = filename


#: (code, lasti) -> Located, or None when the site cannot be parsed.
_SITES = {}

#: filename -> (lines, tree): the parsed source of a file.
_TREES = {}


def locate(frame):
    """The ``with`` statement whose ``__enter__`` ``frame`` is executing, or
    None when its source is not available or the item has no ``as`` name.
    Cached per call site."""
    key = (frame.f_code, frame.f_lasti)
    try:
        return _SITES[key]
    except KeyError:
        pass
    loc = _locate(frame)
    _SITES[key] = loc
    return loc


def _locate(frame):
    code = frame.f_code
    tree = _tree(code.co_filename, frame.f_globals)
    if tree is None:
        return None
    line = frame.f_lineno
    # The with-items entered on this line, in execution order (source order),
    # and the with-entry instructions on it: the k-th instruction enters the
    # k-th item.
    items = [(n, it) for n in sorted(
                 (n for n in ast.walk(tree)
                  if isinstance(n, ast.With) and n.lineno == line),
                 key=lambda n: n.col_offset)
             for it in n.items]
    offsets = [off for off, ln in _with_instrs(code) if ln == line]
    if frame.f_lasti not in offsets or len(offsets) != len(items):
        return None                 # the source does not match the code
    node, item = items[offsets.index(frame.f_lasti)]
    if not isinstance(item.optional_vars, ast.Name):
        return None
    return Located(node, item, item.optional_vars.id, code.co_filename)


def _tree(filename, module_globals):
    lines = linecache.getlines(filename, module_globals)
    if not lines:
        return None
    hit = _TREES.get(filename)
    if hit is not None and hit[0] is lines:
        return hit[1]
    try:
        tree = ast.parse("".join(lines), filename)
    except SyntaxError:
        return None
    _TREES[filename] = (lines, tree)
    return tree


def _with_instrs(code):
    """``(offset, line)`` of each instruction in ``code`` that enters a
    ``with`` item."""
    out = []
    line = None
    for ins in dis.get_instructions(code):
        pos = getattr(ins, "positions", None)
        if pos is not None and pos.lineno is not None:
            line = pos.lineno
        elif ins.starts_line is not None and not isinstance(ins.starts_line, bool):
            line = ins.starts_line
        if ins.opname in _WITH_OPS:
            out.append((ins.offset, line))
    return out
