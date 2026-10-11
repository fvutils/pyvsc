"""SyoSil uniformity grid: x <= y over [0:N-1], count each (x, y) pair.

From the SyoSil whitepaper (v1.0.3.0, §3.4.2): N=10, 10,000 draws, a cell is
"even" if its share is within +-10% of 1/legal_pairs. See
doc/notes/dist_relational_grid_findings.md.

    PYTHONPATH=src python benchmarks/bench_syosil_grid.py                # classic, current backend
    VSC_SOLVER=dv-solve PYTHONPATH=src python benchmarks/bench_syosil_grid.py --n 4 --draws 20000
    ... --front vdc --fresh --rel lt --grid

Prints: even cells / legal cells, busiest and emptiest cell share, chi-square
vs uniform, and the x / y marginals against their exact uniform-over-solutions
values.
"""
import argparse
import sys


def make_classic(n, rel):
    import vsc

    @vsc.randobj
    class Grid:
        def __init__(self):
            self.x = vsc.rand_uint8_t()
            self.y = vsc.rand_uint8_t()

        @vsc.constraint
        def c(self):
            self.x < n
            self.y < n
            if rel == "le":
                self.x <= self.y
            elif rel == "lt":
                self.x < self.y
            elif rel == "ge":
                self.y >= self.x
    return Grid


def make_vdc(n, rel):
    import vsc.dc as vdc
    if rel == "le":
        @vdc.dataclass
        class Grid(vdc.RandClass):
            x: vdc.u8 = vdc.rand()
            y: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.x < n
                self.y < n
                self.x <= self.y
    elif rel == "lt":
        @vdc.dataclass
        class Grid(vdc.RandClass):
            x: vdc.u8 = vdc.rand()
            y: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.x < n
                self.y < n
                self.x < self.y
    else:
        @vdc.dataclass
        class Grid(vdc.RandClass):
            x: vdc.u8 = vdc.rand()
            y: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                self.x < n
                self.y < n
    return Grid


def legal(n, rel, x, y):
    return {"le": x <= y, "ge": x <= y, "lt": x < y, "none": True}[rel]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--draws", type=int, default=10_000)
    ap.add_argument("--rel", choices=["le", "lt", "ge", "none"], default="le")
    ap.add_argument("--front", choices=["classic", "vdc"], default="classic")
    ap.add_argument("--fresh", action="store_true", help="new object per draw")
    ap.add_argument("--grid", action="store_true", help="print the grid")
    a = ap.parse_args()
    n = a.n
    if a.front == "vdc" and a.rel == "ge":
        sys.exit("--rel ge is classic-only")
    cls = (make_vdc if a.front == "vdc" else make_classic)(n, a.rel)

    g = [[0] * n for _ in range(n)]
    obj = cls()
    for _ in range(a.draws):
        if a.fresh:
            obj = cls()
        obj.randomize()
        g[obj.x][obj.y] += 1

    cells = [(x, y) for x in range(n) for y in range(n) if legal(n, a.rel, x, y)]
    bad = sum(g[x][y] for x in range(n) for y in range(n) if not legal(n, a.rel, x, y))
    ideal = a.draws / len(cells)
    shares = [g[x][y] / a.draws * 100 for x, y in cells]
    even = sum(1 for x, y in cells if abs(g[x][y] - ideal) <= 0.1 * ideal)
    chi2 = sum((g[x][y] - ideal) ** 2 / ideal for x, y in cells)
    print("n=%d rel=%s front=%s fresh=%s draws=%d  legal=%d  violations=%d"
          % (n, a.rel, a.front, a.fresh, a.draws, len(cells), bad))
    print("  even %d/%d   busiest %.2f%%  emptiest %.2f%%  ideal %.2f%%  chi2 %.0f (dof %d)"
          % (even, len(cells), max(shares), min(shares), 100 / len(cells), chi2, len(cells) - 1))
    for name, axis in (("x", 0), ("y", 1)):
        obs = [sum(g[x][y] for x, y in cells if (x, y)[axis] == k) / a.draws * 100 for k in range(n)]
        exp = [sum(1 for x, y in cells if (x, y)[axis] == k) / len(cells) * 100 for k in range(n)]
        print("  %s marginal obs: %s" % (name, " ".join("%5.1f" % v for v in obs)))
        print("  %s marginal exp: %s" % (name, " ".join("%5.1f" % v for v in exp)))
    if a.grid:
        for x in range(n):
            print("   " + " ".join("%5.2f" % (g[x][y] * 100 / a.draws) if legal(n, a.rel, x, y)
                                   else "    ." for y in range(n)))


if __name__ == "__main__":
    main()
