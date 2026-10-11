"""
Example 1 — scalar randomization with constraints.

Run:  PYTHONPATH=src python examples/dc/01_alu_txn.py
"""
import vsc.dc as vdc


@vdc.dataclass
class AluTxn(vdc.RandClass):
    op: vdc.u4 = vdc.rand()         # 4-bit unsigned
    a:  vdc.u32 = vdc.rand()
    b:  vdc.u32 = vdc.rand()

    @vdc.constraint
    def c_op(self):
        self.op <= 7                # ALU has 8 operations
        self.a < self.b             # cross-field relation
        self.a.inside(vdc.rangelist(1, 2, (100, 200)))


def main():
    txn = AluTxn()
    for _ in range(5):
        txn.randomize()
        assert txn.op <= 7 and txn.a < txn.b
        assert txn.a in (1, 2) or 100 <= txn.a <= 200
        print(f"op={txn.op:2d}  a={txn.a:5d}  b={txn.b}")

    # Inline (per-call) constraints via randomize_with:
    with txn.randomize_with() as it:
        it.op == 5
        it.a == 2
    assert txn.op == 5 and txn.a == 2
    print(f"inline -> op={txn.op} a={txn.a}")


if __name__ == "__main__":
    main()
