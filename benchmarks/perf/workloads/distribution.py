"""Distribution workloads: `dist` constraints."""
from . import Workload, workload


@workload
class DistWeighted(Workload):
    name, family = "dist_weighted", "distribution"
    fields = ("k",)

    def classic(vsc):
        @vsc.randobj
        class DistWeighted:
            def __init__(self):
                self.k = vsc.rand_uint8_t()

            @vsc.constraint
            def c(self):
                vsc.dist(self.k, [
                    vsc.weight(0, 10), vsc.weight((1, 3), 80), vsc.weight(4, 10)])
        return DistWeighted

    def dc(vdc):
        @vdc.dataclass
        class DistWeighted(vdc.RandClass):
            k: vdc.u8 = vdc.rand()

            @vdc.constraint
            def c(self):
                vdc.dist(self.k, [
                    vdc.weight(0, 10), vdc.weight((1, 3), 80), vdc.weight(4, 10)])
        return DistWeighted

    def cr(cr):
        # constrainedrandom has no dist constraint: a weighted domain is the
        # nearest equivalent (a sampler bias, not a solver input).
        class DistWeighted(cr.RandObj):
            def __init__(self):
                super().__init__()
                self.add_rand_var('k', domain={0: 10, range(1, 4): 80, 4: 10})
        return DistWeighted

    def check(s):
        return 0 <= s["k"] <= 4
