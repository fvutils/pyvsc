'''
Pins the constraint-parser contract for the source-unavailable case (plan §6 #2,
revisited).

The dataclass front-end compiles a ``@vdc.constraint`` from its source AST
(``inspect.getsource``), never by executing it. When the source cannot be read —
the class was defined in a REPL / ``exec`` / ``python -c`` — the constraint cannot
be recovered. Silently dropping it would randomize the fields *unconstrained* (a
wrong result with no error), so the parser raises ``ConstraintParseError`` rather
than warning-and-dropping.

(Earlier design notes described a "warn / Strategy-B fallback"; the implementation
made it a HARD failure instead — this test pins that current contract so it can't
regress to a silent drop.)
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc
from vsc.dc.constraint_parser import ConstraintParseError


class TestSourceUnavailable(DcTestCase):

    # A constrained RandClass whose source is not importable (built via exec).
    _SRC = '''
import vsc.dc as vdc

@vdc.dataclass
class ExecItem(vdc.RandClass):
    a: vdc.u8 = vdc.rand()

    @vdc.constraint
    def a_c(self):
        self.a == 5
'''

    def test_exec_defined_constraint_is_hard_error(self):
        """A constraint on an exec-defined class must raise ConstraintParseError
        (no readable source) — never silently drop the constraint and randomize
        the field unconstrained."""
        ns = {}
        with self.assertRaises(ConstraintParseError):
            exec(compile(self._SRC, "<string>", "exec"), ns)

    def test_module_defined_constraint_is_honored(self):
        """Control: the same shape defined at module scope (source available) is
        compiled via Strategy-A and honored — proves the error above is the
        source-availability path, not a defect in the class itself."""
        @vdc.dataclass
        class ModItem(vdc.RandClass):
            a: vdc.u8 = vdc.rand()

            @vdc.constraint
            def a_c(self):
                self.a == 5

        it = ModItem()
        for _ in range(20):
            it.randomize()
            self.assertEqual(int(it.a), 5)
