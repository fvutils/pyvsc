"""
Example 11 — class constants, read per subclass.

Run:  PYTHONPATH=src python examples/dc/11_class_constants.py
"""
import vsc.dc as vdc


# [const-start]
@vdc.dataclass
class Req(vdc.RandClass):
    MAX_LEN = 16                     # a class attribute: a constant
    MODES = (0, 1)
    length: vdc.u8 = vdc.rand()
    mode: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        1 <= self.length <= self.MAX_LEN
        self.mode in Req.MODES       # the class's own name works too


class LongReq(Req):
    MAX_LEN = 256                    # the same constraint, this subclass's value
    MODES = (2, 3)
# [const-end]


def main():
    r, lr = Req(), LongReq()
    seen = set()
    for _ in range(50):
        r.randomize()
        assert 1 <= r.length <= 16 and r.mode in (0, 1)
        lr.randomize()
        assert 1 <= lr.length <= 255 and lr.mode in (2, 3)
        seen.add(lr.length > 16)
    assert True in seen
    print("ok:", r, lr)


if __name__ == "__main__":
    main()
