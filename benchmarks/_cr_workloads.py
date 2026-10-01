"""Workload definitions for the constrainedrandom comparison
(benchmarks/bench_constrainedrandom.py).

Three implementations of each workload, kept semantically equivalent:

  * ``cr``   -- constrainedrandom ``RandObj``
  * ``vsc``  -- stock pyvsc classic front-end (``@vsc.randobj``), boolector
  * ``vdc``  -- pyvsc dataclass front-end (``vsc.dc``), dv-solve

The first five workloads are transcribed from constrainedrandom's *own*
benchmark suite (``benchmarks/pyvsc/`` in will-keen/constrainedrandom) so the
published 13-50x claims can be reproduced directly. The rest broaden the set
toward problems a constraint solver is actually needed for.

``check`` functions validate every sample so a fast-but-wrong result cannot
win.
"""
import vsc
import vsc.dc as vdc
from constrainedrandom import RandObj, dist as cr_dist_fn
from constrainedrandom.utils import unique as cr_unique


# ---------------------------------------------------------------------------
# 1. basic -- constrainedrandom's VSCBasic ("typically 40-50x faster")
# ---------------------------------------------------------------------------

@vsc.randobj
class vsc_basic(object):
    def __init__(self):
        self.a = vsc.rand_bit_t(8)
        self.b = vsc.rand_bit_t(8)
        self.c = vsc.rand_bit_t(8)
        self.d = vsc.rand_bit_t(8)

    @vsc.constraint
    def ab_c(self):
        self.a < self.b


@vdc.dataclass
class vdc_basic(vdc.RandClass):
    a: vdc.u8 = vdc.rand()
    b: vdc.u8 = vdc.rand()
    c: vdc.u8 = vdc.rand()
    d: vdc.u8 = vdc.rand()

    @vdc.constraint
    def ab_c(self):
        self.a < self.b


class cr_basic(RandObj):
    def __init__(self):
        super().__init__()
        self.add_rand_var('a', bits=8)
        self.add_rand_var('b', bits=8, order=1)
        self.add_rand_var('c', bits=8)
        self.add_rand_var('d', bits=8)
        self.add_constraint(lambda a, b: a < b, ('a', 'b'))


def chk_basic(r):
    assert r['a'] < r['b'], r
    for k in "abcd":
        assert 0 <= r[k] < 256, r


# ---------------------------------------------------------------------------
# 2. in_kw -- constrainedrandom's VSCIn ("typically 13-15x faster")
# ---------------------------------------------------------------------------

@vsc.randobj
class vsc_in(object):
    def __init__(self):
        self.a = vsc.rand_bit_t(8)
        self.b = vsc.rand_bit_t(8)
        self.c = vsc.rand_bit_t(8)
        self.d = vsc.rand_bit_t(8)

    @vsc.constraint
    def ab_c(self):
        self.a in vsc.rangelist(1, 2, vsc.rng(4, 8))
        self.c != 0
        self.d != 0
        self.c < self.d
        self.b in vsc.rangelist(vsc.rng(self.c, self.d))


@vdc.dataclass
class vdc_in(vdc.RandClass):
    a: vdc.u8 = vdc.rand()
    b: vdc.u8 = vdc.rand()
    c: vdc.u8 = vdc.rand()
    d: vdc.u8 = vdc.rand()

    @vdc.constraint
    def ab_c(self):
        self.a.inside(vdc.rangelist(1, 2, vdc.rng(4, 8)))
        self.c != 0
        self.d != 0
        self.c < self.d
        self.b.inside(vdc.rangelist(vdc.rng(self.c, self.d)))


class cr_in(RandObj):
    """CORRECTED transcription.

    constrainedrandom's own benchmark declares this model as
    ``add_rand_var('b', ..., constraints=(lambda b: b != 0,))`` -- i.e. it
    constrains **b**, where the pyvsc model it is timed against constrains
    **c**. The two models are therefore not equivalent, and the published
    version genuinely emits c == 0 solutions (measured: 29/3000). It also
    writes ``b in range(c, d)`` (half-open) against pyvsc's ``rng(c, d)``
    (inclusive). Both are fixed here so the same problem is solved by all
    three configurations."""

    def __init__(self):
        super().__init__()
        self.add_rand_var('a', domain=[1, 2] + list(range(4, 8)))
        self.add_rand_var('b', bits=8)
        self.add_rand_var('c', bits=8, constraints=(lambda c: c != 0,))
        self.add_rand_var('d', bits=8, constraints=(lambda d: d != 0,))
        self.add_constraint(lambda c, d: c < d, ('c', 'd'))
        self.add_constraint(lambda b, c, d: c <= b <= d, ('b', 'c', 'd'))


def chk_in(r):
    assert r['a'] in (1, 2, 4, 5, 6, 7, 8), r
    assert r['c'] != 0 and r['d'] != 0, r
    assert r['c'] < r['d'], r
    assert r['c'] <= r['b'] <= r['d'], r


# ---------------------------------------------------------------------------
# 3. ldinstr -- constrainedrandom's VSCInstr ("typically 13-15x faster")
# ---------------------------------------------------------------------------

SRC0_VALUE = 0xFFFFFBCD


@vsc.randobj
class vsc_ldinstr(object):
    def __init__(self):
        self.imm0 = vsc.rand_bit_t(11)
        self.src0 = vsc.rand_bit_t(5)
        self.dst0 = vsc.rand_bit_t(5)
        self.wb = vsc.rand_bit_t(1)
        self.src0_value_getter = lambda: SRC0_VALUE

    @vsc.constraint
    def wb_src0_dst0(self):
        with vsc.if_then(self.wb == 1):
            self.src0 != self.dst0

    @vsc.constraint
    def sum_src0_imm0(self):
        self.imm0 + self.src0_value_getter() <= 0xFFFFFFFF
        (self.imm0 + self.src0_value_getter()) & 3 == 0


@vdc.dataclass
class vdc_ldinstr(vdc.RandClass):
    imm0: vdc.u11 = vdc.rand()
    src0: vdc.u5 = vdc.rand()
    dst0: vdc.u5 = vdc.rand()
    wb: vdc.u1 = vdc.rand()

    @vdc.constraint
    def wb_src0_dst0(self):
        with vdc.if_then(self.wb == 1):
            self.src0 != self.dst0

    @vdc.constraint
    def sum_src0_imm0(self):
        self.imm0 + 0xFFFFFBCD <= 0xFFFFFFFF
        (self.imm0 + 0xFFFFFBCD) & 3 == 0


class cr_ldinstr(RandObj):
    """constrainedrandom's examples/ldinstr.py (post_randomize elided -- the
    pyvsc versions don't compute the opcode either)."""

    def __init__(self):
        super().__init__()
        self.add_rand_var('src0', bits=5, order=0)
        self.add_rand_var('src0_value', fn=lambda: SRC0_VALUE, order=0)
        self.add_rand_var('wb', bits=1, order=0)
        self.add_rand_var('dst0', bits=5, order=1)
        self.add_rand_var('imm0', bits=11, order=2)
        self.add_constraint(self.wb_dst_src, ('wb', 'dst0', 'src0'))
        self.add_constraint(self.sum_src0_imm0, ('src0_value', 'imm0'))

    def wb_dst_src(self, wb, dst0, src0):
        if wb:
            return dst0 != src0
        return True

    def sum_src0_imm0(self, src0_value, imm0):
        address = src0_value + imm0
        return (address & 3 == 0) and (address < 0xFFFFFFFF)


def chk_ldinstr(r):
    """Checks only the constraints all three models actually share.

    CAVEAT: the `<= 0xFFFFFFFF` overflow guard is a *tautology* in both pyvsc
    front-ends -- the sum is computed in 32-bit arithmetic and wraps, so it is
    always true. constrainedrandom's lambda uses Python bignums, so it really
    does exclude imm0 > 0x432. On this row constrainedrandom therefore solves a
    strictly harder problem than pyvsc does (measured: ~99/200 pyvsc solutions
    overflow 32 bits). The alignment and writeback rules are honored by all
    three, and are what is checked here."""
    assert 0 <= r['imm0'] < (1 << 11), r
    addr = SRC0_VALUE + r['imm0']
    assert addr & 3 == 0, r
    if r['wb']:
        assert r['src0'] != r['dst0'], r


# ---------------------------------------------------------------------------
# 4. listsum -- constrainedrandom's VSCRandListSumZero ("typically 20x")
# ---------------------------------------------------------------------------

@vsc.randobj
class vsc_listsum(object):
    def __init__(self):
        self.listvar = vsc.rand_list_t(vsc.int8_t(), 10)

    @vsc.constraint
    def listvar_c(self):
        with vsc.foreach(self.listvar) as l:
            l >= -10
            l < 11

    @vsc.constraint
    def listvar_sum_c(self):
        # NOTE: constrainedrandom's own benchmark writes `sum(self.listvar) == 0`
        # here. That is the *wrong pyvsc idiom*: Python's builtin sum() builds an
        # expression pyvsc silently discards, so the baseline they time is solving
        # an unconstrained problem (verified: 193/200 samples violate sum==0 on
        # stock pyvsc 0.9.5). `.sum` is the idiom that actually constrains.
        self.listvar.sum == 0


@vdc.dataclass
class vdc_listsum(vdc.RandClass):
    listvar: list[vdc.s8] = vdc.rand(size=10)

    @vdc.constraint
    def listvar_c(self):
        with vdc.foreach(self.listvar) as l:
            l >= -10
            l < 11

    @vdc.constraint
    def listvar_sum_c(self):
        self.listvar.sum == 0


class cr_listsum(RandObj):
    def __init__(self):
        super().__init__()
        self.add_rand_var('listvar', domain=range(-10, 11), length=10)
        self.add_constraint(lambda listvar: sum(listvar) == 0, ('listvar',))


def chk_listsum(r):
    lv = r['listvar']
    assert len(lv) == 10, r
    assert all(-10 <= v <= 10 for v in lv), r
    assert sum(lv) == 0, r


# ---------------------------------------------------------------------------
# 5. listuniq -- constrainedrandom's VSCRandListUnique ("typically 3-4x")
# ---------------------------------------------------------------------------

@vsc.randobj
class vsc_listuniq(object):
    def __init__(self):
        self.listvar = vsc.rand_list_t(vsc.uint8_t(), 10)

    @vsc.constraint
    def listvar_c(self):
        with vsc.foreach(self.listvar) as l:
            l >= 0
            l < 10

    @vsc.constraint
    def listvar_unique_c(self):
        vsc.unique(self.listvar)


@vdc.dataclass
class vdc_listuniq(vdc.RandClass):
    listvar: list[vdc.u8] = vdc.rand(size=10)

    @vdc.constraint
    def listvar_c(self):
        with vdc.foreach(self.listvar) as l:
            l >= 0
            l < 10

    @vdc.constraint
    def listvar_unique_c(self):
        vdc.unique(self.listvar)


class cr_listuniq(RandObj):
    def __init__(self):
        super().__init__()
        self.add_rand_var('listvar', domain=range(10), length=10,
                          list_constraints=[cr_unique])


def chk_listuniq(r):
    lv = r['listvar']
    assert len(lv) == 10 and len(set(lv)) == 10, r
    assert all(0 <= v < 10 for v in lv), r


# ---------------------------------------------------------------------------
# 6/7. wide32 / wide64 -- relational constraints over a large domain
# ---------------------------------------------------------------------------

@vsc.randobj
class vsc_wide32(object):
    def __init__(self):
        self.a = vsc.rand_bit_t(32)
        self.b = vsc.rand_bit_t(32)

    @vsc.constraint
    def c(self):
        self.a < self.b
        self.a > 1000


@vdc.dataclass
class vdc_wide32(vdc.RandClass):
    a: vdc.u32 = vdc.rand()
    b: vdc.u32 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a < self.b
        self.a > 1000


class cr_wide32(RandObj):
    def __init__(self):
        super().__init__()
        self.add_rand_var('a', bits=32, constraints=(lambda a: a > 1000,))
        self.add_rand_var('b', bits=32)
        self.add_constraint(lambda a, b: a < b, ('a', 'b'))


def chk_wide32(r):
    assert 1000 < r['a'] < r['b'] < (1 << 32), r


@vsc.randobj
class vsc_wide64(object):
    def __init__(self):
        self.a = vsc.rand_bit_t(64)
        self.b = vsc.rand_bit_t(64)

    @vsc.constraint
    def c(self):
        self.a < self.b
        self.a > 1000


@vdc.dataclass
class vdc_wide64(vdc.RandClass):
    a: vdc.u64 = vdc.rand()
    b: vdc.u64 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.a < self.b
        self.a > 1000


class cr_wide64(RandObj):
    def __init__(self):
        super().__init__()
        self.add_rand_var('a', bits=64, constraints=(lambda a: a > 1000,))
        self.add_rand_var('b', bits=64)
        self.add_constraint(lambda a, b: a < b, ('a', 'b'))


def chk_wide64(r):
    assert 1000 < r['a'] < r['b'] < (1 << 64), r


# ---------------------------------------------------------------------------
# 8. tight -- a narrow feasible region over a 32-bit domain
#    (word-aligned address in a 4KB window, plus a relational tie)
# ---------------------------------------------------------------------------

@vsc.randobj
class vsc_tight(object):
    def __init__(self):
        self.addr = vsc.rand_bit_t(32)
        self.base = vsc.rand_bit_t(32)

    @vsc.constraint
    def c(self):
        self.base == 0x8000_0000
        self.addr >= self.base
        self.addr < self.base + 0x1000
        (self.addr & 0xFFF) % 64 == 0


@vdc.dataclass
class vdc_tight(vdc.RandClass):
    addr: vdc.u32 = vdc.rand()
    base: vdc.u32 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.base == 0x8000_0000
        self.addr >= self.base
        self.addr < self.base + 0x1000
        (self.addr & 0xFFF) % 64 == 0


class cr_tight(RandObj):
    def __init__(self):
        super().__init__()
        self.add_rand_var('base', bits=32, constraints=(lambda b: b == 0x8000_0000,))
        self.add_rand_var('addr', bits=32)
        self.add_constraint(
            lambda addr, base: base <= addr < base + 0x1000 and (addr & 0xFFF) % 64 == 0,
            ('addr', 'base'))


def chk_tight(r):
    assert r['base'] == 0x8000_0000, r
    assert r['base'] <= r['addr'] < r['base'] + 0x1000, r
    assert (r['addr'] & 0xFFF) % 64 == 0, r


# ---------------------------------------------------------------------------
# 9. alu -- inside-heavy, 32-bit
# ---------------------------------------------------------------------------

@vsc.randobj
class vsc_alu(object):
    def __init__(self):
        self.op = vsc.rand_bit_t(4)
        self.a = vsc.rand_bit_t(32)
        self.b = vsc.rand_bit_t(32)

    @vsc.constraint
    def c(self):
        self.op <= 7
        self.a < self.b
        self.a in vsc.rangelist(1, 2, vsc.rng(100, 200))


@vdc.dataclass
class vdc_alu(vdc.RandClass):
    op: vdc.u4 = vdc.rand()
    a: vdc.u32 = vdc.rand()
    b: vdc.u32 = vdc.rand()

    @vdc.constraint
    def c(self):
        self.op <= 7
        self.a < self.b
        self.a.inside(vdc.rangelist(1, 2, (100, 200)))


class cr_alu(RandObj):
    def __init__(self):
        super().__init__()
        self.add_rand_var('op', bits=4, constraints=(lambda op: op <= 7,))
        self.add_rand_var('a', domain=[1, 2] + list(range(100, 201)))
        self.add_rand_var('b', bits=32)
        self.add_constraint(lambda a, b: a < b, ('a', 'b'))


def chk_alu(r):
    assert r['op'] <= 7, r
    assert r['a'] in (1, 2) or 100 <= r['a'] <= 200, r
    assert r['a'] < r['b'], r


# ---------------------------------------------------------------------------
# 10. dist -- weighted distribution
# ---------------------------------------------------------------------------

@vsc.randobj
class vsc_dist(object):
    def __init__(self):
        self.k = vsc.rand_bit_t(8)

    @vsc.constraint
    def c(self):
        vsc.dist(self.k, [vsc.weight(0, 10), vsc.weight((1, 3), 80), vsc.weight(4, 10)])


@vdc.dataclass
class vdc_dist(vdc.RandClass):
    k: vdc.u8 = vdc.rand()

    @vdc.constraint
    def c(self):
        vdc.dist(self.k, [vdc.weight(0, 10), vdc.weight((1, 3), 80), vdc.weight(4, 10)])


class cr_dist(RandObj):
    """constrainedrandom expresses weighting as a *weighted domain* rather than
    a `dist` constraint. It is a sampler, not a solver input: the weights bias
    the draw, and any constraints on the same variable are then applied by
    rejection, which re-shapes the realized distribution away from the declared
    weights. pyvsc's `dist` is a constraint the solver honors directly."""

    def __init__(self):
        super().__init__()
        self.add_rand_var('k', domain={0: 10, range(1, 4): 80, 4: 10})


def chk_dist(r):
    assert r['k'] in (0, 1, 2, 3, 4), r


# ---------------------------------------------------------------------------
# 11/12. arrays of independent elements
# ---------------------------------------------------------------------------

def _mk_arr(n):
    @vsc.randobj
    class V(object):
        def __init__(self):
            self.arr = vsc.rand_list_t(vsc.uint8_t(), n)

        @vsc.constraint
        def c(self):
            with vsc.foreach(self.arr) as it:
                it > 2
                it < 250

    class C(RandObj):
        def __init__(self):
            super().__init__()
            self.add_rand_var('arr', domain=range(3, 250), length=n)

    V.__name__ = "vsc_arr%d" % n
    C.__name__ = "cr_arr%d" % n
    return V, C


@vdc.dataclass
class vdc_arr32(vdc.RandClass):
    arr: list[vdc.u8] = vdc.rand(size=32)

    @vdc.constraint
    def c(self):
        with vdc.foreach(self.arr) as it:
            it > 2
            it < 250


@vdc.dataclass
class vdc_arr128(vdc.RandClass):
    arr: list[vdc.u8] = vdc.rand(size=128)

    @vdc.constraint
    def c(self):
        with vdc.foreach(self.arr) as it:
            it > 2
            it < 250


vsc_arr32, cr_arr32 = _mk_arr(32)
vsc_arr128, cr_arr128 = _mk_arr(128)


def _chk_arr(n):
    def chk(r):
        arr = r['arr']
        assert len(arr) == n, r
        assert all(2 < v < 250 for v in arr), r
    return chk


# ---------------------------------------------------------------------------
# 13. packet16 -- a realistic mixed sequence item
# ---------------------------------------------------------------------------

@vsc.randobj
class vsc_packet16(object):
    def __init__(self):
        self.kind = vsc.rand_bit_t(4)
        self.addr = vsc.rand_bit_t(32)
        self.length = vsc.rand_bit_t(8)
        self.payload = vsc.rand_list_t(vsc.uint8_t(), 16)

    @vsc.constraint
    def c(self):
        self.kind <= 7
        self.addr > 0x1000
        self.length in vsc.rangelist(vsc.rng(1, 16))
        with vsc.foreach(self.payload) as b:
            b != 0


@vdc.dataclass
class vdc_packet16(vdc.RandClass):
    kind: vdc.u4 = vdc.rand()
    addr: vdc.u32 = vdc.rand()
    length: vdc.u8 = vdc.rand()
    payload: list[vdc.u8] = vdc.rand(size=16)

    @vdc.constraint
    def c(self):
        self.kind <= 7
        self.addr > 0x1000
        self.length.inside(vdc.rangelist((1, 16)))
        with vdc.foreach(self.payload) as b:
            b != 0


class cr_packet16(RandObj):
    def __init__(self):
        super().__init__()
        self.add_rand_var('kind', bits=4, constraints=(lambda k: k <= 7,))
        self.add_rand_var('addr', bits=32, constraints=(lambda a: a > 0x1000,))
        self.add_rand_var('length', domain=range(1, 17))
        self.add_rand_var('payload', domain=range(1, 256), length=16)


def chk_packet16(r):
    assert r['kind'] <= 7 and r['addr'] > 0x1000, r
    assert 1 <= r['length'] <= 16, r
    assert len(r['payload']) == 16 and all(v != 0 for v in r['payload']), r


# ---------------------------------------------------------------------------
# 14. nested -- composition across sub-objects
# ---------------------------------------------------------------------------

@vsc.randobj
class vsc_sub(object):
    def __init__(self):
        self.a = vsc.rand_bit_t(16)
        self.b = vsc.rand_bit_t(16)


@vsc.randobj
class vsc_nested(object):
    def __init__(self):
        self.s1 = vsc_sub()
        self.s2 = vsc_sub()

    @vsc.constraint
    def c(self):
        self.s1.a == self.s2.a


@vdc.dataclass
class vdc_sub(vdc.RandClass):
    a: vdc.u16 = vdc.rand()
    b: vdc.u16 = vdc.rand()


@vdc.dataclass
class vdc_nested(vdc.RandClass):
    s1: vdc_sub = vdc.rand()
    s2: vdc_sub = vdc.rand()

    @vdc.constraint
    def c(self):
        self.s1.a == self.s2.a


class cr_nested_naive(RandObj):
    """constrainedrandom has no object composition: sub-objects must be
    flattened into the parent's namespace by hand.

    Declared the direct way (an equality between two 16-bit vars). The 65536
    domain exceeds max_domain_size (1024), so constrainedrandom falls back to
    random-sample-and-retry and hits the equality with probability 2**-16."""

    def __init__(self):
        super().__init__()
        for nm in ('s1_a', 's1_b', 's2_a', 's2_b'):
            self.add_rand_var(nm, bits=16)
        self.add_constraint(lambda x, y: x == y, ('s1_a', 's2_a'))


class cr_nested(RandObj):
    """The same problem, hand-tuned the way constrainedrandom wants it: s2_a is
    made a *derived* variable that copies s1_a. This is fast, but it is the user
    solving the constraint by hand -- it only works because the relation happens
    to be functional and one-directional. Used as the constrainedrandom number
    so the comparison reflects the library at its best."""

    def __init__(self):
        super().__init__()
        for nm in ('s1_a', 's1_b', 's2_b'):
            self.add_rand_var(nm, bits=16)
        self.add_rand_var('s2_a', fn=lambda x: x, rand_var_args=('s1_a',))


def chk_nested_cr(r):
    assert r['s1_a'] == r['s2_a'], r


def chk_nested_vsc(r):
    assert r['s1'].a == r['s2'].a, r


def chk_nested_vdc(r):
    assert r['s1'].a == r['s2'].a, r


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def extract_one(obj, field):
    """Read a single scalar field off a randomized object of any front-end."""
    if hasattr(obj, "get_results"):
        return obj.get_results()[field]
    return int(getattr(obj, field))


class WL(object):
    def __init__(self, name, cr, vsc_cls, vdc_cls, check, n=1000,
                 check_cr=None, check_vsc=None, check_vdc=None, note=""):
        self.name = name
        self.cr = cr
        self.vsc = vsc_cls
        self.vdc = vdc_cls
        self.check_cr = check_cr or check
        self.check_vsc = check_vsc or check
        self.check_vdc = check_vdc or check
        self.n = n
        self.note = note


# Workloads 1-5 are transcribed from constrainedrandom's own benchmark suite.
CR_SUITE = [
    WL("basic", cr_basic, vsc_basic, vdc_basic, chk_basic, n=2000),
    WL("in_kw", cr_in, vsc_in, vdc_in, chk_in, n=1000),
    WL("ldinstr", cr_ldinstr, vsc_ldinstr, vdc_ldinstr, chk_ldinstr, n=1000),
    WL("listsum", cr_listsum, vsc_listsum, vdc_listsum, chk_listsum, n=300),
    WL("listuniq", cr_listuniq, vsc_listuniq, vdc_listuniq, chk_listuniq, n=300),
]

# Broader set: problems where a real solver is the point.
BROAD_SUITE = [
    WL("wide32", cr_wide32, vsc_wide32, vdc_wide32, chk_wide32, n=2000),
    WL("wide64", cr_wide64, vsc_wide64, vdc_wide64, chk_wide64, n=2000),
    WL("tight", cr_tight, vsc_tight, vdc_tight, chk_tight, n=200),
    WL("alu", cr_alu, vsc_alu, vdc_alu, chk_alu, n=1000),
    WL("dist", cr_dist, vsc_dist, vdc_dist, chk_dist, n=2000),
    WL("arr32", cr_arr32, vsc_arr32, vdc_arr32, _chk_arr(32), n=500),
    WL("arr128", cr_arr128, vsc_arr128, vdc_arr128, _chk_arr(128), n=200),
    WL("packet16", cr_packet16, vsc_packet16, vdc_packet16, chk_packet16, n=500),
    WL("nested", cr_nested, vsc_nested, vdc_nested, None, n=1000,
       check_cr=chk_nested_cr, check_vsc=chk_nested_vsc, check_vdc=chk_nested_vdc,
       note="cr hand-tuned as a derived var; see cr_nested_naive"),
]

ALL = CR_SUITE + BROAD_SUITE
