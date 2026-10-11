import vsc, vsc.dc as vdc, random
from enum import IntEnum
vsc.set_solver_backend("dv-solve")
class E(IntEnum):
    A=0;B=1;C=2;D=3;E_=4;F=5;G=6;H=7

def mk(elem, default):
    @vdc.dataclass
    class C(vdc.RandClass):
        x: elem = vdc.rand()
        tbl: list[elem] = vdc.field(default_factory=lambda: list(default))
        @vdc.constraint
        def c(self):
            self.x.inside(vdc.rangelist(self.tbl))
    return C

for label, elem, default, inst in [
    ("u8 default [1,2]  inst default", vdc.u8, [1,2], None),
    ("u8 default []     inst [1,2]", vdc.u8, [], [1,2]),
    ("u8 default [1,2]  inst [5,6,7]", vdc.u8, [1,2], [5,6,7]),
    ("u8 default [1,2,3] inst [5]", vdc.u8, [1,2,3], [5]),
    ("enum default [A,B] inst default", E, [E.A,E.B], None),
    ("enum default []   inst [A,B]", E, [], [E.A,E.B]),
]:
    C = mk(elem, default)
    seen = set()
    for k in range(60):
        c = C() if inst is None else C(tbl=list(inst))
        c.randomize(); seen.add(int(c.x))
    exp = set(int(v) for v in (default if inst is None else inst))
    print(f"{label:35s} expected {sorted(exp)} got {sorted(seen)[:12]}{'...' if len(seen)>12 else ''}  {'OK' if seen<=exp else 'WRONG'}")
