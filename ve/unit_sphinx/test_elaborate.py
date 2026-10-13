"""vsc.sphinx.elaborate: exact counts from the runtime model, and classic
fields / coverpoints from one instance. No Sphinx."""
import pytest

import vsc_doc_fixture as G
import vsc_elab_fixture as F
from vsc.impl.coverage_registry import CoverageRegistry
from vsc.sphinx import elaborate as E
from vsc.sphinx import introspect as I
from vsc.sphinx import render as R


def _by_name(items):
    return {i.name: i for i in items}


@pytest.fixture
def registry():
    """The global coverage registry before the test, to check it is left
    untouched."""
    reg = CoverageRegistry.inst()
    before = {k: list(v) for k, v in reg.covergroup_type_m.items()}
    yield reg, before
    assert CoverageRegistry.inst() is reg
    assert {k: list(v) for k, v in reg.covergroup_type_m.items()} == before


# --- Dataclass covergroups --------------------------------------------------


def test_auto_width_bins():
    cps = _by_name(E.elaborate_covergroup(F.ElabCov).coverpoints)
    assert cps["auto8"].n_bins == 64
    assert cps["auto8"].auto_bins == "64 bins of 4 values over 0..255"
    assert cps["auto_s4"].n_bins == 16
    assert cps["auto_s4"].auto_bins == "16 bins of 1 value over -8..7"
    assert cps["uneven"].n_bins == 3
    assert cps["uneven"].auto_bins == "3 bins of 85 to 87 values over 0..255"


def test_auto_enum_bins_with_exclusion():
    cps = _by_name(E.elaborate_covergroup(F.ElabCov).coverpoints)
    assert cps["kind"].n_bins == 2
    assert cps["kind"].auto_bins == "2 bins, one per member of Kind (1 excluded)"
    # No exclusion: no note.
    alu = _by_name(E.elaborate_covergroup(G.AluCov).coverpoints)
    assert alu["op"].auto_bins == "4 bins, one per member of Op"


def test_explicit_bins_after_exclusion():
    cp = _by_name(E.elaborate_covergroup(F.ElabCov).coverpoints)["val"]
    assert cp.n_bins == 7
    assert cp.auto_bins is None
    counts = {b.name: b.count for b in cp.bins}
    assert counts == {"each": 7, "gone": 0}
    # Ignore bins are counted from their spec; elaboration leaves them.
    assert [(b.name, b.count) for b in cp.ignore] == [("skip", 1)]


def test_cross_counts():
    x = _by_name(E.elaborate_covergroup(F.ElabCov).crosses)["kind_x_val"]
    assert (x.n_bins, x.n_ignore, x.n_illegal) == (14, 7, 4)
    x = _by_name(E.elaborate_covergroup(G.AluCov).crosses)["op_x_mode"]
    assert (x.n_bins, x.n_ignore, x.n_illegal) == (8, 1, 0)


def test_elaborated_flag_and_static_description_unchanged():
    d = E.elaborate_covergroup(F.ElabCov)
    assert d.elaborated
    s = I.describe_covergroup(F.ElabCov)
    assert not s.elaborated
    assert all(cp.n_bins is None for cp in s.coverpoints)
    assert all(x.n_bins is None for x in s.crosses)
    # Statically, a per-value bin_array has no count and exclusions are not
    # applied; the rest of the description is the same.
    each = _by_name(_by_name(s.coverpoints)["val"].bins)["each"]
    assert each.count == 8
    assert [c.name for c in d.coverpoints] == [c.name for c in s.coverpoints]
    assert [c.ref_src for c in d.coverpoints] == [c.ref_src for c in s.coverpoints]


def test_no_user_code_and_no_registration(registry):
    calls = F.ElabCov.post_init_calls
    E.elaborate_covergroup(F.ElabCov)
    E.elaborate_covergroup(F.DefaultsCov)
    assert F.ElabCov.post_init_calls == calls       # __post_init__ not run


def test_matches_a_real_instance(registry):
    """Elaborated counts are the counts of a constructed instance, and
    constructing instances (which trims bin specs in place) does not change
    later elaboration."""
    first = E.elaborate_covergroup(F.ElabCov)
    with E.scratch_registry():
        cg = F.ElabCov()
    for cp in first.coverpoints:
        assert cg._cp_insts[cp.name]._model.get_n_bins() == cp.n_bins, cp.name
    for x in first.crosses:
        m = cg._cr_insts[x.name]._model
        assert (m.n_bins, m.n_ignore, m.n_illegal) == \
            (x.n_bins, x.n_ignore, x.n_illegal)
    assert E.elaborate_covergroup(F.ElabCov) == first


def test_selection_reads_field_default():
    x = E.elaborate_covergroup(F.DefaultsCov).crosses[0]
    assert (x.n_bins, x.n_ignore, x.n_illegal) == (16, 4, 0)


def test_failure_raises_elaboration_error(registry):
    with pytest.raises(E.ElaborationError) as info:
        E.elaborate_covergroup(F.BrokenCov)
    msg = str(info.value)
    assert "vsc_elab_fixture.BrokenCov" in msg and "AttributeError" in msg
    assert isinstance(info.value.__cause__, AttributeError)


def test_selection_reading_a_non_coverpoint_is_shown_as_written():
    for cls in (F.DefaultsCov, F.BrokenCov):
        sel = I.describe_covergroup(cls).crosses[0].ignore[0]
        assert "object at" not in sel.expr
        assert sel.expr.startswith("vdc.binsof(s.a).intersect([(0, s.")


def test_apply_models_skips_missing_models():
    d = I.describe_covergroup(G.AluCov)
    out = E.apply_models(d, {}, {})
    assert out.elaborated
    assert out.coverpoints == d.coverpoints and out.crosses == d.crosses


# --- Classic randobj --------------------------------------------------------


def test_classic_fields(registry):
    d = E.instantiate_classic_randobj(F.ClassicPkt)
    assert d.classic and d.instantiated
    f = _by_name(d.fields)
    assert list(f) == ["addr", "data", "extra", "mode", "count", "offset"]
    assert (f["addr"].type_str, f["addr"].kind) == ("u12", "rand")
    assert f["data"].type_str == "u8[4]" and f["data"].size is None
    assert (f["extra"].type_str, f["extra"].size) == ("u8[]", "random")
    assert (f["mode"].type_str, f["mode"].type_ref) == \
        ("Mode", "vsc_elab_fixture.Mode")
    assert (f["count"].kind, f["count"].default) == ("state", "5")
    assert (f["offset"].type_str, f["offset"].default) == ("s8", None)
    assert all(x.owner is F.ClassicPkt for x in d.fields)
    # Constraints are those of the static description.
    assert [c.name for c in d.constraints] == ["c_addr"]
    assert d.member_names() == list(f) + ["c_addr"]


def test_classic_constructor_defaults_are_used():
    d = E.instantiate_classic_randobj(G.Classic)     # __init__(self, width=8)
    assert [(x.name, x.type_str, x.kind) for x in d.fields] == [("a", "u8", "rand")]


def test_classic_composite_fields():
    f = _by_name(E.instantiate_classic_randobj(F.ClassicSub).fields)
    hdr = "vsc_elab_fixture.ClassicHdr"
    assert (f["hdr"].type_str, f["hdr"].type_ref, f["hdr"].kind) == \
        ("ClassicHdr", hdr, "rand")
    assert (f["hdrs"].type_str, f["hdrs"].type_ref, f["hdrs"].kind) == \
        ("ClassicHdr[2]", hdr, "rand")
    assert (f["meta"].type_str, f["meta"].kind) == ("ClassicHdr", "state")


def test_classic_inherited_fields():
    d = E.instantiate_classic_randobj(F.ClassicSub)
    f = _by_name(d.fields)
    assert list(f)[-4:] == ["tag", "hdr", "hdrs", "meta"]
    assert f["tag"].owner is F.ClassicSub
    base = I.classic_user_class(F.ClassicPkt)
    assert f["addr"].owner is base
    assert f["addr"].owner.__qualname__ == "ClassicPkt"


def test_classic_instantiate_failure():
    with pytest.raises(E.ElaborationError) as info:
        E.instantiate_classic_randobj(F.NeedsInit)
    assert "NeedsInit" in str(info.value)
    assert isinstance(info.value.__cause__, TypeError)


# --- Classic covergroup -----------------------------------------------------


def test_classic_covergroup_detection_and_static():
    assert I.is_classic_covergroup(F.ClassicCov)
    assert not I.is_classic_covergroup(F.ClassicPkt)
    assert not I.is_classic_randobj(F.ClassicCov)
    d = I.describe_classic_covergroup(F.ClassicCov)
    assert d.classic and not d.elaborated
    assert d.member_names() == []


def test_classic_covergroup(registry):
    d = E.instantiate_classic_covergroup(F.ClassicCov)
    assert d.classic and d.elaborated
    assert d.sample == (("addr", "u12", None),
                        ("mode", "Mode", "vsc_elab_fixture.Mode"))
    assert [(f.name, f.kind) for f in d.fields] == \
        [("addr", "sample_arg"), ("mode", "sample_arg")]

    cps = _by_name(d.coverpoints)
    assert list(cps) == ["cp_addr", "cp_mode", "cp_auto"]
    a = cps["cp_addr"]
    assert (a.type_str, a.push, a.ref_src) == ("u12", False, "self.addr")
    assert [(b.name, b.kind, b.values, b.count, b.doc) for b in a.bins] == [
        ("low", "bin", "0..255", 1, "first page"),
        ("rest", "bin_array", "256..4095", 3, None)]
    assert a.n_bins == 4 and a.crossed_by == ("cr",)
    assert cps["cp_mode"].auto_bins == "2 bins, one per member of Mode"
    assert cps["cp_auto"].auto_bins == "64 bins of 64 values over 0..4095"
    assert cps["cp_auto"].crossed_by == ()

    x = d.crosses[0]
    assert (x.name, x.components) == ("cr", ("cp_addr", "cp_mode"))
    assert (x.n_bins, x.n_ignore, x.n_illegal) == (8, 1, 0)
    assert [(s.name, s.expr) for s in x.ignore] == [
        ("low_wr", "a.intersect([(0, 0xff)]) and m.intersect([1])")]
    assert d.member_names() == ["addr", "mode", "cp_addr", "cp_mode", "cp_auto",
                                "cr", "sample"]


# --- Class source -----------------------------------------------------------


def test_class_source_reads_init_assignments():
    src = I._ClassSource.of(I.classic_user_class(F.ClassicPkt))
    assert {"addr", "data", "extra", "mode", "count", "offset", "helper"} <= \
        set(src.self_assigns)
    assert src.segment(src.call_arg("addr", 0, "t")) == "12"
    # Class-level assignments are unaffected for dataclass classes.
    src = I._ClassSource.of(G.AluCov)
    assert src.self_assigns == {}
    assert "op" in src.assigns


# --- Rendering of elaborated facts -------------------------------------------


def test_render_cross_bins_text():
    x = I.CrossDesc("x", object, ("a", "b"))
    assert R.cross_bins_text(x) is None
    import dataclasses
    rep = dataclasses.replace
    assert R.cross_bins_text(rep(x, n_bins=8, n_ignore=0, n_illegal=0)) == "8"
    assert R.cross_bins_text(rep(x, n_bins=8, n_ignore=1, n_illegal=0)) == \
        "8: 7 counted, 1 ignored"
    assert R.cross_bins_text(rep(x, n_bins=14, n_ignore=7, n_illegal=4)) == \
        "14: 3 counted, 7 ignored, 4 illegal"
    assert R.cross_bins_text(rep(x, n_bins=4, n_ignore=0, n_illegal=4)) == \
        "4: 0 counted, 4 illegal"


def test_render_elaborated_covergroup():
    text = "\n".join(R.render_covergroup(E.elaborate_covergroup(F.ElabCov),
                                         R.Options()))
    assert ":bins: automatic, 64 bins of 4 values over 0..255" in text
    assert ":bins: 7" in text                       # explicit, elaborated
    assert ":bins: 14: 3 counted, 7 ignored, 4 illegal" in text
    assert "0 (all values excluded)" in text
    # Static rendering keeps the estimates.
    text = "\n".join(R.render_covergroup(I.describe_covergroup(F.ElabCov),
                                         R.Options()))
    assert ":bins: automatic, 64 bins over 0..255" in text
    assert "counted" not in text and "excluded" not in text


def test_render_classic_covergroup_sample_text():
    lines = R.render_covergroup(E.instantiate_classic_covergroup(F.ClassicCov),
                                R.Options())
    assert ".. py:method:: sample(addr: u12, mode: Mode)" in lines
    text = "\n".join(lines)
    assert "pass a value for each sampling input, in order" in text
    assert "by keyword" not in text
