"""
Example 5 — the full constrained-random + coverage loop: randomize a transaction,
then sample a covergroup that reads through to it (cg_arg), until covered.

Run:  PYTHONPATH=src python examples/dc/05_crv_loop.py
"""
import vsc.dc as vdc


@vdc.dataclass
class Txn(vdc.RandClass):
    op: vdc.u4 = vdc.rand()
    addr: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.op <= 3
        self.addr < 64


@vdc.dataclass
class TxnCov(vdc.Covergroup):
    txn: Txn = vdc.cg_arg()                      # read-through to the live object
    op_cp: vdc.Coverpoint[vdc.u4] = vdc.coverpoint(
        lambda s: s.txn.op, bins=dict(ops=vdc.bin_array([], [0, 3])))
    addr_cp: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
        lambda s: s.txn.addr,
        bins=dict(lo=vdc.bin([0, 31]), hi=vdc.bin([32, 63])))


def main():
    import random
    random.seed(0)

    txn = Txn()
    cov = TxnCov(txn=txn)

    n = 0
    while cov.get_coverage() < 100 and n < 1000:
        txn.randomize()
        cov.sample()
        n += 1

    print(f"reached {cov.get_coverage()}% coverage after {n} transactions")
    assert cov.get_coverage() == 100


if __name__ == "__main__":
    main()
