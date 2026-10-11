"""
Example 12 — the same class in classic pyvsc and in vdc.

Run:  PYTHONPATH=src python examples/dc/12_porting.py
"""
import vsc
import vsc.dc as vdc


# [classic-start]
@vsc.randobj
class ClassicTxn(object):
    def __init__(self):
        self.kind = vsc.rand_uint8_t()
        self.addr = vsc.rand_uint16_t()
        self.data = vsc.rand_list_t(vsc.uint8_t(), 4)

    @vsc.constraint
    def c(self):
        self.kind.inside(vsc.rangelist(1, 2, 4))
        with vsc.if_then(self.kind == 4):
            self.addr < 0x100
        with vsc.else_then:
            self.addr >= 0x100
        with vsc.foreach(self.data) as x:
            x != 0
        (self.addr > 0x10) & (self.addr != 0x200)
# [classic-end]


# [vdc-start]
@vdc.dataclass
class VdcTxn(vdc.RandClass):
    kind: vdc.u8 = vdc.rand()
    addr: vdc.u16 = vdc.rand()
    data: list[vdc.u8] = vdc.rand(size=4)

    @vdc.constraint
    def c(self):
        self.kind in {1, 2, 4}
        if self.kind == 4:
            self.addr < 0x100
        else:
            self.addr >= 0x100
        for x in self.data:
            x != 0
        self.addr > 0x10 and self.addr != 0x200
# [vdc-end]


def _check(t):
    assert t.kind in (1, 2, 4)
    assert (t.addr < 0x100) if t.kind == 4 else (t.addr >= 0x100)
    assert all(x != 0 for x in t.data)
    assert t.addr > 0x10 and t.addr != 0x200


def main():
    c, v = ClassicTxn(), VdcTxn()
    for _ in range(30):
        c.randomize()
        _check(c)
        v.randomize()
        _check(v)
    print("ok:", v)


if __name__ == "__main__":
    main()
