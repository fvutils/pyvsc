"""vsc.sphinx.introspect: description objects from pyvsc classes, no Sphinx."""
import importlib.util
import os

import pytest

import vsc_doc_fixture as F
from vsc.dc import constraint_ir as ir
from vsc.sphinx import introspect as I

EX_DIR = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "..", "examples", "dc"))


def _load_example(fname):
    spec = importlib.util.spec_from_file_location("ex_" + fname[:-3],
                                                  os.path.join(EX_DIR, fname))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _by_name(items):
    return {i.name: i for i in items}


def test_detection():
    assert I.is_randclass(F.AluTxn)
    assert I.is_randclass(F.WideTxn)
    assert not I.is_randclass(F.AluCov)
    assert I.is_covergroup(F.AluCov)
    assert not I.is_covergroup(F.AluTxn)
    assert I.is_classic_randobj(F.Classic)
    assert I.classic_user_class(F.Classic).__name__ == "Classic"
    assert not I.is_randclass(F.Op) and not I.is_covergroup(F.Op)


def test_fields():
    d = I.describe_randclass(F.AluTxn)
    f = _by_name(d.fields)
    assert list(f) == ["op", "a", "b", "tags", "mode"]
    assert (f["op"].type_str, f["op"].type_ref, f["op"].kind) == \
        ("Op", "vsc_doc_fixture.Op", "rand")
    assert (f["a"].type_str, f["a"].domain) == ("u32", "1..1000")
    assert (f["tags"].type_str, f["tags"].size) == ("u8[]", "random, <= 4")
    assert (f["mode"].kind, f["mode"].default) == ("state", "1")
    assert f["a"].constrained_by == ("c_op", "c_small")
    assert f["op"].constrained_by == ()


def test_constraints():
    d = I.describe_randclass(F.AluTxn)
    c_op, = d.constraints
    c_small, = d.generics
    assert (c_op.kind, c_op.signature) == ("fixed", "")
    assert c_op.doc == "Operands ascending; both small."
    assert c_op.source == "self.a < self.b\nself.c_small(64)"
    assert c_op.fields_read == ("a", "b")
    assert c_op.generics_used == ("c_small",)
    assert (c_small.kind, c_small.signature) == ("generic", "(n=16)")
    assert c_small.used_by == ("c_op",)


def test_inheritance_and_override():
    d = I.describe_randclass(F.WideTxn)
    f = _by_name(d.fields)
    assert f["op"].owner is F.AluTxn and f["w"].owner is F.WideTxn
    c_op, = d.constraints
    assert c_op.owner is F.WideTxn and c_op.overrides is F.AluTxn
    assert c_op.doc is None         # an override does not inherit the docstring
    assert c_op.fields_read == ("a", "b", "w")
    c_small, = d.generics
    assert c_small.owner is F.AluTxn


def test_covergroup():
    d = I.describe_covergroup(F.AluCov)
    assert d.sample == (("op", "Op", "vsc_doc_fixture.Op"), ("mode", "int", None),
                        ("x", "int", None))
    assert [f.name for f in d.fields] == ["x"]
    assert d.fields[0].kind == "sample_arg"
    cp = _by_name(d.coverpoints)
    assert cp["op"].push and cp["op"].auto_bins == "one bin per member of Op"
    assert cp["op"].sample_index == 0
    lo, hi = cp["mode"].bins
    assert (lo.name, lo.values, lo.count, lo.doc) == ("lo", "0, 1", 1, "idle modes")
    assert (hi.doc) == "Active modes."          # doc= wins over a comment
    val = cp["val"]
    assert not val.push
    assert (val.ref_src, val.iff_src) == ("s.x + 1", "s.x != 0")
    assert val.bins[0].count == 4 and val.bins[0].kind == "bin_array"
    assert val.options == (("weight", 2),)
    x, = d.crosses
    assert x.components == ("op", "mode")
    assert cp["mode"].crossed_by == ("op_x_mode",)
    sel, = x.ignore
    assert sel.expr == ("binsof(op).intersect([0]) & "
                        "binsof(mode).intersect([(0, 1)])")
    assert sel.doc == "ADD never runs in the idle modes"


def test_classic():
    d = I.describe_classic_randobj(F.Classic)
    c = _by_name(d.constraints)
    assert list(c) == ["ab_c", "small"]
    assert (c["ab_c"].kind, c["small"].kind) == ("fixed", "dynamic")
    assert c["ab_c"].owner is F.Classic
    assert c["ab_c"].fields_read is None
    assert c["ab_c"].source == "self.a < 10"


def test_binsof_text():
    from vsc.dc.coverage.descriptors import _BinsofTerm
    probe = I._Probe()
    a, b = _BinsofTerm(probe.a), _BinsofTerm(probe.b)
    assert I.binsof_str(a & (b | ~a)) == "binsof(a) & (binsof(b) | ~binsof(a))"
    assert I.binsof_str(~(a & b)) == "~(binsof(a) & binsof(b))"


def test_bin_doc_keyword():
    import vsc
    assert vsc.bin(1, doc="one").doc == "one"
    assert vsc.bin_array([2], (0, 3), doc="two").doc == "two"
    assert vsc.wildcard_bin("0b1x", doc="w").doc == "w"
    assert vsc.bin(1).doc is None


def test_ir_queries():
    tm = F.AluTxn._vsc_type_model
    c_op = tm.constraints[0]
    assert ir.fields_read(c_op) == [("a",), ("b",)]
    assert ir.refs_used(c_op) == ["c_small"]


@pytest.mark.parametrize("fname", sorted(
    f for f in os.listdir(EX_DIR) if f.endswith(".py")) if os.path.isdir(EX_DIR) else [])
def test_examples_describe(fname):
    """Every class in examples/dc describes without error."""
    mod = _load_example(fname)
    for obj in vars(mod).values():
        if getattr(obj, "__module__", None) != mod.__name__:
            continue
        if I.is_randclass(obj):
            d = I.describe_randclass(obj)
            for c in d.constraints + d.generics:
                assert c.source is not None, (fname, c.name)
        elif I.is_covergroup(obj):
            I.describe_covergroup(obj)
