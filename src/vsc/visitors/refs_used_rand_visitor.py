'''
Does an expression read a field the solver chooses?

An array subscript or bit-select whose index reads such a field is symbolic: its
index has no value until the solve. Its index's current value, from before the
solve, must not be used to pick an element or a bit.
'''
from vsc.model.model_visitor import ModelVisitor


class RefsUsedRandVisitor(ModelVisitor):

    def __init__(self):
        super().__init__()
        self._found = False

    def refs_used_rand(self, e) -> bool:
        self._found = False
        e.accept(self)
        return self._found

    def visit_expr_fieldref(self, e):
        if getattr(e.fm, "is_used_rand", False):
            self._found = True


def refs_used_rand(e) -> bool:
    """True when ``e`` reads a field that is random in the current solve."""
    return RefsUsedRandVisitor().refs_used_rand(e)
