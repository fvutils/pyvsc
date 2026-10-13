"""vsc.sphinx end to end: build small projects and check the doctree, the
Python domain's records and the warnings. Runs on Sphinx 7, 8 and 9."""
import pytest

M = "vsc_doc_fixture"


def _objects(app):
    return {k: v.objtype for k, v in app.env.get_domain("py").objects.items()}


def _warnings(app):
    return [l for l in app._warning.getvalue().splitlines() if "WARNING" in l]


def _html(app, doc="index"):
    return (app.outdir / ("%s.html" % doc)).read_text(encoding="utf-8")


@pytest.mark.sphinx("html", testroot="basic", confoverrides={"nitpicky": True})
def test_automodule(app):
    app.build()
    assert _warnings(app) == []
    objs = _objects(app)
    expect = {
        "AluTxn": "randclass", "AluTxn.op": "randfield", "AluTxn.a": "randfield",
        "AluTxn.mode": "randfield", "AluTxn.c_op": "constraint",
        "AluTxn.c_small": "constraint", "AluTxn.helper": "method",
        "AluTxn.pre_randomize": "method",
        "WideTxn": "randclass", "WideTxn.w": "randfield",
        "WideTxn.c_op": "constraint",
        "AluCov": "covergroup", "AluCov.op": "coverpoint",
        "AluCov.mode": "coverpoint", "AluCov.val": "coverpoint",
        "AluCov.op_x_mode": "cross", "AluCov.x": "randfield",
        "AluCov.sample": "method",
        "Classic": "randclass", "Classic.ab_c": "constraint",
        "Classic.small": "constraint", "Op": "class",
    }
    for k, t in expect.items():
        assert objs.get("%s.%s" % (M, k)) == t, k
    # pyvsc machinery is never documented; inherited members are not
    # repeated on the subclass without :inherited-members:
    for k in ("AluTxn.randomize", "AluTxn.set_rand_mode", "AluCov.get_coverage",
              "WideTxn.op", "WideTxn.c_small", "Classic.randomize",
              "Classic.get_model"):
        assert "%s.%s" % (M, k) not in objs, k

    html = _html(app)
    assert "_Width" not in html and "Annotated" not in html
    # cross-links: field -> constraint, inherited summary row -> base entry
    assert 'href="#%s.AluTxn.c_op"' % M in html
    assert 'href="#%s.AluTxn.op"' % M in html
    assert "idle modes" in html and "Active modes." in html
    assert "binsof(op).intersect([0])" in html
    assert 'class="py class randclass"' in html
    assert 'class="py class covergroup"' in html


@pytest.mark.sphinx("html", testroot="auto", confoverrides={"nitpicky": True})
def test_auto_directives(app):
    app.build()
    warnings = _warnings(app)
    assert len(warnings) == 1 and "Op is not a rand class" in warnings[0], warnings
    objs = _objects(app)
    assert objs["%s.AluTxn.c_op" % M] == "constraint"
    assert objs["handmade.Pkt"] == "randclass"
    assert objs["handmade.Pkt.len"] == "randfield"
    assert objs["handmade.Pkt.c_len"] == "constraint"
    html = _html(app)
    assert "self.a &lt; self.b" not in html          # :constraint-show-source: none
    assert "»" in html                          # :constraint-signature-fields:
    assert "Active modes." not in html               # :coverpoint-show-bins: false
    assert 'href="#handmade.Pkt.c_len"' in html
    # :members: w, c_op with :exclude-members: c_op -> only w
    assert objs["%s.WideTxn.w" % M] == "randfield"
    assert "%s.WideTxn.c_op" % M not in objs


@pytest.mark.sphinx("html", testroot="inherited", confoverrides={"nitpicky": True})
def test_inherited_and_config(app):
    app.build()
    assert _warnings(app) == []
    objs = _objects(app)
    # :inherited-members: renders the base's fields and constraints here
    assert objs["%s.WideTxn.op" % M] == "randfield"
    assert objs["%s.WideTxn.c_small" % M] == "constraint"
    assert "%s.WideTxn.randomize" % M not in objs
    html = _html(app)
    assert "bit [31:0]" in html                      # vsc_type_style = "sv"
    assert "<details>" in html                       # collapsed source
    assert "Inherited from" in html


@pytest.mark.sphinx("html", testroot="basic",
                    confoverrides={"vsc_autodoc_enable": False})
def test_disabled(app):
    app.build()
    objs = _objects(app)
    assert objs["%s.AluTxn" % M] == "class"
    assert "%s.AluTxn.c_op" % M not in objs or \
        objs["%s.AluTxn.c_op" % M] == "method"


try:
    import sphinx
    _SPHINX9 = sphinx.version_info >= (9,)
except ImportError:  # pragma: no cover
    _SPHINX9 = False


@pytest.mark.skipif(not _SPHINX9, reason="Sphinx 9's legacy autodoc switch")
@pytest.mark.sphinx("html", testroot="basic",
                    confoverrides={"nitpicky": True,
                                   "autodoc_use_legacy_class_based": True})
def test_sphinx9_legacy_autodoc(app):
    app.build()
    assert _warnings(app) == []
    objs = _objects(app)
    assert objs["%s.AluTxn.c_op" % M] == "constraint"
    assert objs["%s.AluCov.op_x_mode" % M] == "cross"
    assert "%s.AluTxn.randomize" % M not in objs
