"""
Example 8 — set membership: 'in' with lists, sets, ranges and named constants.

Run:  PYTHONPATH=src python examples/dc/08_grammar_sets.py
"""
import vsc.dc as vdc

# Read when the class is defined, like any constant a constraint names.
LEGAL_OPCODES = (0x03, 0x13, 0x23, 0x33, 0x63)


# [sets-start]
@vdc.dataclass
class Instr(vdc.RandClass):
    opcode: vdc.u8 = vdc.rand()
    rd: vdc.u8 = vdc.rand()
    imm: vdc.u16 = vdc.rand()
    shamt: vdc.u8 = vdc.rand()
    align: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.opcode in LEGAL_OPCODES          # a named constant collection
        self.rd in range(1, 32)               # half-open, as in Python: 1..31
        self.imm in vdc.r[0x100:0x1FF]        # inclusive, as in SystemVerilog
        self.shamt not in {0, 31}             # a set literal; 'not in'
        self.align in range(0, 64, 8)         # a step: 0, 8, ..., 56
# [sets-end]


def main():
    t = Instr()
    for _ in range(50):
        t.randomize()
        assert t.opcode in LEGAL_OPCODES
        assert 1 <= t.rd <= 31
        assert 0x100 <= t.imm <= 0x1FF
        assert t.shamt not in (0, 31)
        assert t.align % 8 == 0 and t.align < 64
    print("ok:", t)


if __name__ == "__main__":
    main()
