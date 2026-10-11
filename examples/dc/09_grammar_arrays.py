"""
Example 9 — arrays: 'for' loops, len / sum, all / any, indexing.

Run:  PYTHONPATH=src python examples/dc/09_grammar_arrays.py
"""
import vsc.dc as vdc


# [arrays-start]
@vdc.dataclass
class Frame(vdc.RandClass):
    data: list[vdc.u8] = vdc.rand(max_size=16)
    flags: list[vdc.u1] = vdc.rand(size=4)
    idx: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        4 <= len(self.data) <= 12            # the array's size
        sum(self.data) == 200
        for x in self.data:                  # every element
            x < 100
        for i in range(len(self.data)):      # by index
            if i > 0:
                self.data[i] != self.data[i - 1]
        0 in self.data                       # at least one element is 0
        any(f == 1 for f in self.flags)      # (a fixed-size array)
        self.data[-1] > 50                   # counts from the end
        self.idx < len(self.data)
        self.data[self.idx] == 7             # a random index
# [arrays-end]


def main():
    f = Frame()
    for _ in range(20):
        f.randomize()
        d = list(f.data)
        assert 4 <= len(d) <= 12 and sum(d) == 200
        assert all(x < 100 for x in d)
        assert all(d[i] != d[i - 1] for i in range(1, len(d)))
        assert 0 in d and d[-1] > 50 and 1 in list(f.flags)
        assert f.idx < len(d) and d[f.idx] == 7
    print("ok:", list(f.data), f.idx)


if __name__ == "__main__":
    main()
