"""
Example 3 — nested (composite) rand objects and arrays of them.

Run:  PYTHONPATH=src python examples/dc/03_nested.py
"""
import vsc.dc as vdc


@vdc.dataclass
class Register(vdc.RandClass):
    addr: vdc.u8 = vdc.rand()
    data: vdc.u32 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.addr < 16


@vdc.dataclass
class Block(vdc.RandClass):
    base: Register = vdc.rand()                 # scalar nested object
    regs: list[Register] = vdc.rand(size=4)     # array of nested objects

    @vdc.constraint
    def c(self):
        # Cross-object + cross-element relations.
        self.base.addr == 0
        with vdc.foreach(self.regs, idx=True) as i:
            self.regs[i].addr == i + 1


def main():
    blk = Block()
    blk.randomize()
    assert blk.base.addr == 0
    print(f"base: addr={blk.base.addr} data={blk.base.data}")
    for i, r in enumerate(blk.regs):
        assert r.addr == i + 1
        print(f"reg[{i}]: addr={r.addr} data={r.data}")


if __name__ == "__main__":
    main()
