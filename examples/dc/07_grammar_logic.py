"""
Example 7 — logic in a constraint: and / or / not, if / elif / else, match.

A constraint body is parsed, never run: each Python construct means the
constraint it reads as. See doc/source/dataclass/constraints.rst.

Run:  PYTHONPATH=src python examples/dc/07_grammar_logic.py
"""
from enum import IntEnum

import vsc.dc as vdc


class Kind(IntEnum):
    READ = 0
    WRITE = 1
    FENCE = 2


# [logic-start]
@vdc.dataclass
class BusOp(vdc.RandClass):
    kind: Kind = vdc.rand()
    addr: vdc.u16 = vdc.rand()
    size: vdc.u8 = vdc.rand()
    burst: vdc.u1 = vdc.rand()

    @vdc.constraint
    def c_logic(self):
        self.size in {1, 2, 4, 8}
        # 'and' / 'or' / 'not' are logical.
        self.addr < 0x100 or self.addr >= 0xF000
        not (self.kind == Kind.FENCE and self.burst)

    @vdc.constraint
    def c_kind(self):
        # if / elif / else; an 'if' without 'else' is an implication.
        if self.kind == Kind.FENCE:
            self.size == 1
        elif self.burst:
            self.size >= 4
        else:
            self.size <= 4
        if self.size == 8:
            self.addr % 8 == 0
# [logic-end]


# [match-start]
@vdc.dataclass
class Packet(vdc.RandClass):
    kind: Kind = vdc.rand()
    length: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c_len(self):
        match self.kind:
            case Kind.READ:
                self.length == 0
            case Kind.WRITE:
                1 <= self.length <= 64
            case _:
                self.length == 4
# [match-end]


def main():
    op = BusOp()
    for _ in range(50):
        op.randomize()
        assert op.size in (1, 2, 4, 8)
        assert op.addr < 0x100 or op.addr >= 0xF000
        assert not (op.kind == Kind.FENCE and op.burst)
        if op.kind == Kind.FENCE:
            assert op.size == 1
        elif op.burst:
            assert op.size >= 4
        else:
            assert op.size <= 4
        if op.size == 8:
            assert op.addr % 8 == 0
    p = Packet()
    for _ in range(30):
        p.randomize()
        if p.kind == Kind.READ:
            assert p.length == 0
        elif p.kind == Kind.WRITE:
            assert 1 <= p.length <= 64
        else:
            assert p.length == 4
    print("ok:", op, p)


if __name__ == "__main__":
    main()
