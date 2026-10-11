"""
Example 10 — randomize_with: per-call constraints with caller values.

The body is parsed with the same grammar as a @vdc.constraint body, and
never run. A sub-expression that names neither 'it' nor a loop name
(base + 4*i, allowed, self.window()) is ordinary Python, evaluated once per
call in the caller's scope.

Run:  PYTHONPATH=src python examples/dc/10_inline.py
"""
import vsc.dc as vdc


@vdc.dataclass
class Access(vdc.RandClass):
    addr: vdc.u32 = vdc.rand()
    size: vdc.u8 = vdc.rand()
    write: vdc.u1 = vdc.rand()


# [inline-start]
class Driver:
    def __init__(self, base, allowed_sizes):
        self.base = base
        self.allowed = allowed_sizes

    def window(self):
        return 0x100

    def next_access(self, acc, i, read_only):
        with acc.randomize_with() as it:
            it.addr >= self.base + 4 * i
            it.addr < self.base + 4 * i + self.window()
            it.size in self.allowed
            if read_only:
                not it.write
            for s in (3, 5):
                it.size != s
        return acc
# [inline-end]


def main():
    d = Driver(0x8000, [1, 2, 4, 8])
    acc = Access()
    for i in range(10):
        d.next_access(acc, i, read_only=(i % 2 == 0))
        lo = 0x8000 + 4 * i
        assert lo <= acc.addr < lo + 0x100
        assert acc.size in (1, 2, 4, 8)
        if i % 2 == 0:
            assert acc.write == 0
    print("ok:", acc)


if __name__ == "__main__":
    main()
