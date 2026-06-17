'''
Dataclass-front-end parallel of ve/unit/test_constraint_override.py.

Pins the inheritance/override semantics (plan §6 open-question #5): a subclass
@vdc.constraint with the SAME name as a base-class constraint REPLACES it (MRO-merged
collection in type_model.py), while a new-named constraint is added. Must match the
legacy @vsc.randobj behavior.

Note: the classic ``test_docs_example`` also exercises *re-assigning fields in
__init__* — a legacy per-instance mechanism with no dataclass analogue (dc declares
fields as class annotations). The portable, important behavior it checks is constraint
override, which the dc twin pins by re-declaring the fields as annotations on the
subclass and overriding the constraint.
'''
from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestConstraintOverride(DcTestCase):

    def test_basics(self):

        @vdc.dataclass
        class my_base_s(vdc.RandClass):
            a: vdc.u16 = vdc.rand()
            b: vdc.u16 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a < self.b

        @vdc.dataclass
        class my_ext_s(my_base_s):
            c: vdc.u16 = vdc.rand()

            @vdc.constraint
            def ab_c(self):           # overrides base ab_c (a < b)
                self.a > self.b

            @vdc.constraint
            def ac_c(self):
                self.c == self.a

        base = my_base_s()
        for i in range(100):
            base.randomize()
            self.assertLess(base.a, base.b)

        ext = my_ext_s()
        for i in range(100):
            ext.randomize()
            self.assertGreater(ext.a, ext.b)
            self.assertEqual(ext.a, ext.c)

    def test_docs_example(self):
        # Constraint override across inheritance: the subclass ab_c (a > b)
        # replaces the base ab_c (a < b). (The classic twin also re-assigns fields
        # in __init__; that is a legacy-only per-instance mechanism — the dc model
        # carries fields per type, so the override is the portable behavior here.)

        @vdc.dataclass
        class my_base_s(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()
            d: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):
                self.a < self.b

        @vdc.dataclass
        class my_ext_s(my_base_s):

            @vdc.constraint
            def ab_c(self):
                self.a > self.b

        inst = my_ext_s()
        inst.randomize()

        self.assertGreater(inst.a, inst.b)
