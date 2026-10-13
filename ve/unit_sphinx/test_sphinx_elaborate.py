"""vsc_covergroup_elaborate / vsc_classic_instantiate end to end: off by
default, on from conf.py or per class, failures warned once and documented
statically. Runs on Sphinx 7, 8 and 9."""
import pytest
import sphinx

from vsc.impl.coverage_registry import CoverageRegistry

M = "vsc_elab_fixture"
BOTH = {"vsc_covergroup_elaborate": True, "vsc_classic_instantiate": True,
        "nitpicky": True}


def _objects(app):
    return {k[len(M) + 1:]: v.objtype
            for k, v in app.env.get_domain("py").objects.items()
            if k.startswith(M + ".")}


def _warnings(app):
    return [l for l in app._warning.getvalue().splitlines() if "WARNING" in l]


def _html(app, doc="index"):
    return (app.outdir / ("%s.html" % doc)).read_text(encoding="utf-8")


@pytest.mark.sphinx("html", testroot="elab", confoverrides={"nitpicky": True})
def test_off_by_default(app):
    app.build()
    assert _warnings(app) == []
    objs = _objects(app)
    html = _html(app)
    # Static estimates; no cross totals.
    assert "64 bins over 0..255" in html
    assert "of 4 values" not in html and "counted" not in html
    # Classic classes: constraints only, no fields or coverpoints (autodoc
    # still documents a #:-commented instance attribute, as a plain
    # attribute); a classic covergroup is typed as one and its pyvsc
    # machinery is hidden.
    assert objs["ClassicPkt"] == "randclass"
    assert objs["ClassicPkt.c_addr"] == "constraint"
    assert objs.get("ClassicPkt.addr") == "attribute"
    assert "ClassicPkt.extra" not in objs
    assert objs["ClassicCov"] == "covergroup"
    assert objs.get("ClassicCov.cp_addr") == "attribute"
    for k in ("ClassicCov.cp_mode", "ClassicCov.sample", "ClassicCov.with_sample",
              "ClassicCov.get_coverage", "ClassicCov.get_model"):
        assert k not in objs, k


@pytest.mark.sphinx("html", testroot="elab", confoverrides=BOTH)
def test_elaborate_and_instantiate(app):
    # Build against an empty registry: it must still be empty afterwards (the
    # registry dedupes types, so comparing a non-empty one proves little).
    saved = CoverageRegistry._inst
    CoverageRegistry._inst = None
    try:
        app.build()
        registered = dict(CoverageRegistry.inst().covergroup_type_m)
    finally:
        CoverageRegistry._inst = saved
    assert registered == {}
    objs = _objects(app)
    html = _html(app)

    # Exact counts.
    assert "64 bins of 4 values over 0..255" in html
    assert "2 bins, one per member of Kind (1 excluded)" in html
    assert "14: 3 counted, 7 ignored, 4 illegal" in html
    assert "0 (all values excluded)" in html
    assert "16: 12 counted, 4 ignored" in html          # reads a default

    # Classic randobj fields, with their #: comments from __init__, each
    # documented once.
    for f in ("addr", "data", "extra", "mode", "count", "offset"):
        assert objs["ClassicPkt.%s" % f] == "randfield", f
    assert "ClassicPkt.helper" not in objs
    assert html.count('id="%s.ClassicPkt.addr"' % M) == 1
    assert "Target address." in html and "Payload bytes." in html
    # A subclass documents its own field; inherited ones link to the base.
    assert objs["ClassicSub.tag"] == "randfield"
    assert "ClassicSub.addr" not in objs
    assert 'href="#%s.ClassicPkt.addr"' % M in html

    # Classic covergroup.
    expect = {"ClassicCov": "covergroup", "ClassicCov.addr": "randfield",
              "ClassicCov.mode": "randfield", "ClassicCov.cp_addr": "coverpoint",
              "ClassicCov.cp_mode": "coverpoint", "ClassicCov.cp_auto": "coverpoint",
              "ClassicCov.cr": "cross", "ClassicCov.sample": "method"}
    for k, t in expect.items():
        assert objs.get(k) == t, k
    for k in ("ClassicCov.with_sample", "ClassicCov.get_coverage",
              "ClassicCov.buildable_l"):
        assert k not in objs, k
    assert "Address ranges." in html and "first page" in html
    assert "64 bins of 64 values over 0..4095" in html
    assert "8: 7 counted, 1 ignored" in html

    # Failures: warned once each, documented statically.
    warnings = _warnings(app)
    assert len(warnings) == 2, warnings
    if sphinx.version_info >= (8,):   # Sphinx 7 does not print the type
        assert all("[vsc.elaborate]" in w for w in warnings)
    assert any("BrokenCov" in w and "AttributeError" in w for w in warnings)
    assert any("NeedsInit" in w and "TypeError" in w for w in warnings)
    assert objs["BrokenCov.a_x_b"] == "cross"
    assert objs["NeedsInit"] == "randclass"



@pytest.mark.sphinx("html", testroot="elab",
                    confoverrides=dict(BOTH, suppress_warnings=["vsc.elaborate"]))
def test_failures_can_be_suppressed(app):
    app.build()
    assert _warnings(app) == []


@pytest.mark.sphinx("html", testroot="elab-directive",
                    confoverrides={"nitpicky": True})
def test_per_class_options(app):
    app.build()
    assert _warnings(app) == []
    objs = _objects(app)
    html = _html(app)
    # :covergroup-elaborate: on ElabCov only.
    assert "14: 3 counted, 7 ignored, 4 illegal" in html
    assert "16: 12 counted" not in html
    # :classic-instantiate: on ClassicPkt and ClassicCov.
    assert objs["ClassicPkt.addr"] == "randfield"
    assert objs["ClassicCov.cp_addr"] == "coverpoint"
    assert "8: 7 counted, 1 ignored" in html
