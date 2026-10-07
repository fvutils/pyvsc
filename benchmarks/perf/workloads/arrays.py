"""Array workloads: fixed-size lists with element constraints."""
from . import Workload, workload


@workload
class Arr8(Workload):
    name, family = "arr8", "arrays"
    fields = ("arr",)

    def classic(vsc):
        @vsc.randobj
        class Arr8:
            def __init__(self):
                self.arr = vsc.rand_list_t(vsc.uint8_t(), 8)

            @vsc.constraint
            def c(self):
                with vsc.foreach(self.arr) as it:
                    it > 2
                    it < 250
        return Arr8

    def dc(vdc):
        @vdc.dataclass
        class Arr8(vdc.RandClass):
            arr: list[vdc.u8] = vdc.rand(size=8)

            @vdc.constraint
            def c(self):
                with vdc.foreach(self.arr) as it:
                    it > 2
                    it < 250
        return Arr8

    def cr(cr):
        class Arr8(cr.RandObj):
            def __init__(self):
                super().__init__()
                self.add_rand_var('arr', domain=range(3, 250), length=8)
        return Arr8

    def check(s):
        return len(s["arr"]) == 8 and all(2 < v < 250 for v in s["arr"])
