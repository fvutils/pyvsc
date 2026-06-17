"""
``vdc.Covergroup`` — the coverage capability base class for the dataclass
front-end. Provides ``sample()`` / ``get_coverage()`` / ``get_inst_coverage()``.

Per the coverage seam (``memory/dc-coverage-reuse-sv-model.md``): the *structure*
is elaborated once on ``cls._vsc_cg_type_model`` (see ``type_model``); this module
materializes the per-instance *runtime* — for now the classic, SV-1800-faithful
``CovergroupModel``/``CoverpointModel`` tree, which we drive declaratively and
delegate sampling + coverage math to. ``_build_runtime`` is the single seam a
flat-count / native collector would later replace; ``sample()`` already takes plain
scalar values, so that boundary is stable.
"""
from vsc.impl.coverage_registry import CoverageRegistry
from vsc.impl.enum_info import EnumInfo
from vsc.model.coverage_options_model import CoverageOptionsModel
from vsc.model.covergroup_model import CovergroupModel
from vsc.model.coverpoint_bin_collection_model import CoverpointBinCollectionModel
from vsc.model.coverpoint_bin_enum_model import CoverpointBinEnumModel
from vsc.model.coverpoint_cross_model import CoverpointCrossModel
from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.expr_ref_model import ExprRefModel
from vsc.model.rangelist_model import RangelistModel

from .descriptors import Coverpoint, Cross


class Covergroup:
    """Inherit to make a ``@vdc.dataclass`` a covergroup."""

    def __post_init__(self):
        # dataclass __init__ has set cg_arg/sample_arg/field values; now build the
        # per-instance coverage runtime. (Subclasses overriding __post_init__ must
        # call super().__post_init__().)
        self._build_runtime()

    # -- the runtime seam --------------------------------------------------

    def _build_runtime(self):
        tm = type(self)._vsc_cg_type_model
        cg = CovergroupModel(type(self).__name__)
        self._cp_insts = {}
        self._cr_insts = {}
        for desc in tm.coverpoints:
            model = _build_coverpoint_model(self, desc)
            cg.add_coverpoint(model)
            self._cp_insts[desc.name] = Coverpoint(desc.name, model, desc.enum_cls)
        # Crosses reference the just-built coverpoint runtime objects by lambda;
        # add them before finalize() so the cross product is enumerated.
        for cdesc in tm.crosses:
            model = _build_cross_model(self, cdesc)
            cg.add_coverpoint(model)   # routes to cross_l via isinstance
            self._cr_insts[cdesc.name] = Cross(cdesc.name, model)
        cg.finalize()
        # Register with the global CoverageRegistry: hooks the instance up to its
        # type covergroup (type-level aggregation, reporting, UCIS export — the
        # same path the classic front-end uses). The registry is reset per test by
        # ctor.test_setup().
        CoverageRegistry.inst().register_cg(cg)
        self._cg_model = cg

    # -- sampling ----------------------------------------------------------

    def sample(self, *args, **kwargs):
        """Bind any provided push-coverpoint / sample_arg formals (positional in
        declaration order, then by name), then run the core sampling pass. Unset
        formals keep their previous value."""
        tm = type(self)._vsc_cg_type_model
        formals = tm.sample_formals
        if len(args) > len(formals):
            raise TypeError("sample() takes at most %d positional args (%d given)"
                            % (len(formals), len(args)))
        for i, v in enumerate(args):
            self._apply_formal(formals[i], v)
        for name, v in kwargs.items():
            f = tm.formal_by_name.get(name)
            if f is None:
                raise TypeError("sample() got an unexpected argument %r" % name)
            self._apply_formal(f, v)
        self._sample_now()

    def _apply_formal(self, formal, value):
        kind, name = formal
        if kind == "cp":
            self._cp_insts[name].set(value)
        else:   # "arg" — a sample_arg field
            object.__setattr__(self, name, value)

    def _sample_now(self):
        """Run the structure-driven sampling pass (used by an overridden
        ``sample()`` after assigning state)."""
        self._cg_model.sample()

    def assign_from(self, src, names=None):
        """Copy ``src.<name>`` into each sample_arg field (or the named subset)."""
        tm = type(self)._vsc_cg_type_model
        for kind, name in tm.sample_formals:
            if kind != "arg":
                continue
            if names is not None and name not in names:
                continue
            if hasattr(src, name):
                object.__setattr__(self, name, getattr(src, name))

    # -- coverage ----------------------------------------------------------

    def get_inst_coverage(self):
        """Coverage of *this* instance (SV get_inst_coverage)."""
        return self._cg_model.get_inst_coverage()

    def get_coverage(self):
        """Cumulative (type) coverage across all instances of this covergroup type
        (SV get_coverage). Equals get_inst_coverage() for a single instance."""
        return self._cg_model.get_coverage()


def _build_cross_model(obj, cdesc):
    """Build a CoverpointCrossModel from the cross's targets (resolved via their
    lambdas to the just-built runtime objects). A target may be a coverpoint or
    another cross — nested crosses are flattened to their component coverpoints
    (matching classic ``cross``'s flatten_targets). ``binsof`` cross ignore/illegal
    selections are a back-end stub in classic (no parity target), so unsupported."""
    options = _make_options(cdesc)
    model = CoverpointCrossModel(cdesc.name, options, None, None)
    for target in cdesc.targets:
        for cp_model in _flatten_cross_target(target(obj), cdesc.name):
            model.add_coverpoint(cp_model)
    return model


def _flatten_cross_target(rt, cname):
    if isinstance(rt, Coverpoint):
        return [rt._model]
    if isinstance(rt, Cross):
        # Component coverpoint models of the nested cross, in order.
        return list(rt._model.coverpoint_model_l)
    raise TypeError(
        "cross %r target must resolve to a coverpoint or cross (got %r)"
        % (cname, type(rt).__name__))


def _make_options(desc):
    options = CoverageOptionsModel()
    if desc.options:
        for k, v in desc.options.items():
            setattr(options, k, v)
    return options


def _value_getter(obj, desc):
    """A callable returning the coverpoint's current integer value: the staged push
    value, or the evaluated pull ``ref`` (enum members map through EnumInfo)."""
    if desc.is_push:
        name = desc.name
        return lambda: obj._cp_insts[name]._staged
    ref = desc.ref
    if desc.enum_cls is not None:
        ei = EnumInfo.get(desc.enum_cls)
        def get_enum():
            v = ref(obj)
            return v if isinstance(v, int) else ei.e2v(v)
        return get_enum
    return lambda: int(ref(obj))


def _build_coverpoint_model(obj, desc):
    """Replicate the classic (SV-1800-faithful) CoverpointModel assembly from a
    declarative descriptor: target ref, options, iff, and bins — explicit
    (``vdc.bin``/``vdc.bin_array``) or automatic (enum cardinality / width-derived
    via ``auto_bin_max``). See vsc/coverage.py:coverpoint.build_cov_model."""
    options = _make_options(desc)
    target = ExprRefModel(_value_getter(obj, desc), desc.width or 32, desc.signed)
    iff_e = None
    if desc.iff is not None:
        iff_fn = desc.iff
        iff_e = ExprRefModel(lambda: 1 if iff_fn(obj) else 0, 1, False)

    model = CoverpointModel(target, desc.name, options, iff_e)

    # ignore_bins + illegal_bins contribute their values to an exclusion set that
    # trims the normal/auto bins (SV §19.5.5/§19.5.6); they are also added as
    # dedicated ignore/illegal bin models.
    exclude = RangelistModel()
    _collect_exclude(exclude, desc.ignore_bins)
    _collect_exclude(exclude, desc.illegal_bins)
    if exclude.range_l:
        exclude.compact()

    if desc.bins:
        # Explicit bins: each spec's build_cov_model encodes SV bin semantics.
        for bname, spec in desc.bins.items():
            _require_spec(desc, bname, spec)
            bm = spec.build_cov_model(model, bname, exclude)
            if bm is not None:
                model.add_bin_model(bm)
    elif desc.enum_cls is not None:
        # Auto enum bins: one bin per enumerator (SV §19.5.3).
        ei = EnumInfo.get(desc.enum_cls)
        enum_bins = RangelistModel()
        for member in desc.enum_cls:
            enum_bins.add_value(ei.e2v(member))
        enum_bins.compact()
        if exclude.range_l:
            enum_bins.intersect(exclude)
        names = {ei.e2v(m): m.name for m in desc.enum_cls}
        for r in enum_bins.range_l:
            v = r[0]
            model.add_bin_model(CoverpointBinEnumModel(names.get(v, str(v)), v))
    else:
        # Auto width-derived bins: N = min(2^width, auto_bin_max), uniformly
        # distributed (SV §19.5.3) — built by the classic collection factory.
        binspec = RangelistModel()
        if not desc.signed:
            binspec.add_range(0, (1 << desc.width) - 1)
        else:
            low = 1 << (desc.width - 1)
            binspec.add_range(-low, low - 1)
        if exclude.range_l:
            binspec.intersect(exclude)
        model.add_bin_model(CoverpointBinCollectionModel.mk_collection(
            desc.name, binspec, options.auto_bin_max))

    # Dedicated ignore/illegal bin models (no exclusion applied to themselves).
    if desc.ignore_bins:
        for bname, spec in desc.ignore_bins.items():
            _require_spec(desc, bname, spec)
            bm = spec.build_cov_model(model, bname, None)
            if bm is not None:
                model.add_ignore_bin_model(bm)
    if desc.illegal_bins:
        for bname, spec in desc.illegal_bins.items():
            _require_spec(desc, bname, spec)
            bm = spec.build_cov_model(model, bname, None)
            if bm is not None:
                model.add_illegal_bin_model(bm)

    return model


def _require_spec(desc, bname, spec):
    if not hasattr(spec, "build_cov_model"):
        raise TypeError(
            "coverpoint %r bin %r is not a vdc.bin/bin_array/wildcard_bin spec"
            % (desc.name, bname))


def _collect_exclude(exclude, bins_dict):
    """Add the values/ranges of each ``vdc.bin`` in an ignore/illegal dict to the
    exclusion rangelist (matches classic coverpoint.build_cov_model)."""
    if not bins_dict:
        return
    for spec in bins_dict.values():
        ranges = getattr(spec, "range_l", None)
        if ranges is None:
            continue
        for r in ranges:
            if isinstance(r, (tuple, list)):
                exclude.add_range(r[0], r[1])
            else:
                exclude.add_value(r)
