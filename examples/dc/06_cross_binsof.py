"""
Example 6 — cross bin selection with binsof (SV-1800 §19.6).

A cross ignore_bins / illegal_bins is {name: lambda s: <binsof expr>}.
binsof(s.cp) selects a component coverpoint (whole, or narrowed with .intersect);
& | ~ combine selections. Ignored cross bins drop out of coverage; illegal cross
bins drop out *and* their hits are tracked.

Run:  PYTHONPATH=src python examples/dc/06_cross_binsof.py
"""
import inspect

import vsc.dc as vdc


@vdc.dataclass
class AddrCov(vdc.Covergroup):
    # Two address coverpoints, 4 uniform bins each over 0..255
    # (bin k covers [k*64 .. k*64+63]); a 4x4 = 16-bin cross.
    src: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
        bins=dict(s=vdc.bin_array([4], (0, 255))))
    dst: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
        bins=dict(d=vdc.bin_array([4], (0, 255))))

    src_x_dst: vdc.Cross = vdc.cross(
        lambda s: s.src, lambda s: s.dst,
        # Don't care about low-src/high-dst transfers: ignore that one cross bin.
        ignore_bins=dict(
            dontcare=lambda s: vdc.binsof(s.src).intersect([(0, 63)])
                             & vdc.binsof(s.dst).intersect([(192, 255)])),
        # A transfer to itself in the top page is illegal: track if it ever happens.
        illegal_bins=dict(
            self_top=lambda s: vdc.binsof(s.src).intersect([(192, 255)])
                             & vdc.binsof(s.dst).intersect([(192, 255)])))


def main():
    cov = AddrCov()

    # The synthesized sample() carries the real formals.
    assert list(inspect.signature(cov.sample).parameters) == ["src", "dst"]

    m = cov.src_x_dst._model
    print(f"cross bins = {m.n_bins}, ignored = {m.n_ignore}, illegal = {m.n_illegal}")
    assert (m.n_bins, m.n_ignore, m.n_illegal) == (16, 1, 1)

    # Hit every src/dst bin combination (bin k -> value k*64).
    for sk in range(4):
        for dk in range(4):
            cov.sample(sk * 64, dk * 64)

    # 16 bins - 1 ignored - 1 illegal = 14 valid, all hit -> 100%.
    print(f"cross coverage = {cov.src_x_dst.get_coverage()}%")
    assert cov.src_x_dst.get_coverage() == 100

    # The illegal bin (src & dst both in the top page) was hit once and tracked.
    illegal_idx = 3 * 4 + 3   # (src bin 3, dst bin 3)
    print(f"illegal hits = {m.get_illegal_bin_hits(illegal_idx)}")
    assert m.get_illegal_bin_hits(illegal_idx) == 1


if __name__ == "__main__":
    main()
