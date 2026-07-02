"""
``randc`` (cyclic random) support for the dataclass front-end.

A SystemVerilog ``randc`` variable iterates through all the values in its
(constraint-satisfying) domain in a random order, repeating no value until every
value has been produced; once the domain is exhausted a fresh permutation begins.

Two implementations coexist:

* **Fast path (separable randc)** -- when a ``randc`` field is *separable* (no
  constraint ever couples it to another rand field: its constraints mention only
  itself and non-rand state) and all its constraints are atomic boolean
  expressions, we derive its exact feasible domain without the SMT solver. The
  candidate domain comes from bound propagation for a scalar field (a superset --
  it does not model interior ``!=`` holes) or from the member set for an enum
  field; we then filter it by *evaluating* the field's constraints at each
  candidate value. We walk a shuffled sample-without-replacement over the resulting
  true domain and hand each draw to the solver as a fixed input (``rand_mode`` off)
  -- so cycling costs **no per-draw SMT solve**.

* **Exclusion path (fallback)** -- for coupled randc, non-atomic or non-evaluable
  constraints (e.g. ``inside``), over-cap scalar domains, or any object the fast
  path can't handle, we fall back to value exclusion: per instance remember the
  values produced this cycle and add a ``field != v`` term for each on every solve;
  UNSAT means the cycle is complete, so clear history and re-solve. Correct but
  pays a solve per draw.

The fast path is engaged **all-or-nothing** per object per solve. A ``SolveFailure``
(or any evaluation error) under the fast path reverts to exclusion, so a mis-judged
separability can never produce a wrong result -- only a slower one.

Limitation (exclusion path): with multiple randc fields, exhausting one resets the
history of all. Single-randc-field objects are exact.

See ``doc/notes/verilator_test_adaptation_plan.md`` (randc cyclic support).
"""
from vsc.impl.enum_info import EnumInfo
from vsc.model.bin_expr_type import BinExprType
from vsc.model.constraint_block_model import ConstraintBlockModel
from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.field_composite_model import FieldCompositeModel
from vsc.model.model_visitor import ModelVisitor
from vsc.model.randomizer import Randomizer
from vsc.model.solve_failure import SolveFailure
from vsc.visitors.variable_bound_visitor import VariableBoundVisitor

# Exclusion path: a scalar randc wider than this is never pre-reset by declared
# size; its history is bounded only by the constraint-satisfying domain, closed
# each cycle by UNSAT-reset.
_MAX_SIZE_RESET_BITS = 16

# Fast path: the candidate domain (from bound propagation) is materialized and
# filtered; a larger candidate defers to the exclusion path rather than iterate it.
_MAX_FAST_DOMAIN = 1 << 16


def _randc_names(tm):
    return [fd.name for fd in tm.fields
            if fd.rand_kind == "randc"
            and not fd.is_array and not fd.is_composite]


def enabled_randc_names(obj, tm):
    """Names of this object's ``randc`` scalar/enum fields that are currently
    rand-enabled (a rand_mode(0) field holds its value and is not cycled)."""
    names = _randc_names(tm)
    if not names:
        return names
    rm = getattr(obj, "_vsc_rand_mode", None)
    if rm:
        names = [n for n in names if rm.get(n, True)]
    return names


# ---------------------------------------------------------------------------
# Exclusion path (fallback)
# ---------------------------------------------------------------------------

def _domain_size(fd):
    if fd.enum_cls is not None:
        return len(EnumInfo.get(fd.enum_cls).e2v_m)
    if fd.bits <= _MAX_SIZE_RESET_BITS:
        return 1 << fd.bits
    return None


def _reset_exhausted(tm, used):
    """Clear history for any field that has produced its whole declared domain."""
    idx = tm.field_index
    for name, vals in used.items():
        if not vals:
            continue
        ds = _domain_size(tm.fields[idx[name]])
        if ds is not None and len(vals) >= ds:
            used[name] = set()


def _build_block(tm, used, field_models, names):
    """A ``__randc__`` constraint block excluding every value already produced in
    the current cycle, or ``None`` if there is nothing to exclude yet."""
    idx = tm.field_index
    block = None
    for name in names:
        vals = used.get(name)
        fm = field_models.get(name)
        if not vals or fm is None:
            continue
        fd = tm.fields[idx[name]]
        for v in vals:
            if block is None:
                block = ConstraintBlockModel("__randc__")
            block.constraint_l.append(ConstraintExprModel(ExprBinModel(
                ExprFieldRefModel(fm), BinExprType.Ne,
                ExprLiteralModel(int(v), fd.signed, fd.bits))))
    return block


def _record(used, field_models, names):
    """Remember the just-solved value of each ``randc`` field (in solver domain,
    so enum members and raw scalars are tracked uniformly)."""
    for name in names:
        fm = field_models.get(name)
        if fm is not None:
            used.setdefault(name, set()).add(int(fm.get_val()))


# ---------------------------------------------------------------------------
# Fast path (separable randc): bound-domain candidate + evaluation filter
# ---------------------------------------------------------------------------

class _RandRefCollector(ModelVisitor):
    """Collect the rand-*enabled* field models referenced by a constraint."""

    def __init__(self):
        super().__init__()
        self.refs = set()

    def visit_expr_fieldref(self, e):
        fm = e.fm
        if getattr(fm, "is_declared_rand", False) and getattr(fm, "rand_mode", False):
            self.refs.add(fm)


def _rand_refs(stmt):
    c = _RandRefCollector()
    stmt.accept(c)
    return c.refs


def _all_blocks(composite):
    """Every constraint block in the composite tree (this level + nested composites)."""
    blocks = list(composite.constraint_model_l)
    for f in composite.field_l:
        if isinstance(f, FieldCompositeModel):
            blocks.extend(_all_blocks(f))
    return blocks


def _fast_analysis(names, name2fm, blocks):
    """For each randc field, decide separability and collect its atomic constraints.

    Returns ``(fast, cons)`` where ``fast`` is the set of names that are both
    separable (never co-occur with another rand field in a statement) and whose
    every referencing statement is an atomic ``ConstraintExprModel``; ``cons`` maps
    each such name to the list of atomic constraints referencing it (for filtering).
    """
    target = {name2fm[n]: n for n in names if n in name2fm}
    ok = set(target.values())
    cons = {n: [] for n in target.values()}
    for blk in blocks:
        for stmt in blk.constraint_l:
            refs = _rand_refs(stmt)
            here = [target[fm] for fm in refs if fm in target]
            if not here:
                continue
            if len(refs) > 1:                 # coupled to another rand field
                for n in here:
                    ok.discard(n)
            if isinstance(stmt, ConstraintExprModel):
                for n in here:
                    cons[n].append(stmt)
            else:                             # non-atomic (scope/foreach/...)
                for n in here:
                    ok.discard(n)
    return ok, cons


def _bounds(composite, base):
    v = VariableBoundVisitor()
    v.process([composite], base, False)
    return v.bound_m


def _candidate_ranges(bound):
    """Bound-propagation's candidate interval-set (superset) + its value count."""
    bound.update()
    rl = sorted([r[0], r[1]] for r in bound.domain.range_l)
    merged = []
    for lo, hi in rl:
        if merged and lo <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    size = sum(hi - lo + 1 for lo, hi in merged)
    return merged, size


def _range_values(ranges):
    for lo, hi in ranges:
        yield from range(lo, hi + 1)


def _feasible_values(fm, candidates, cons_list):
    """Filter ``candidates`` (an iterable of solver-domain ints) to the values that
    actually satisfy the field's constraints, by evaluating each constraint with the
    field set to the candidate. May raise if a constraint expression is not evaluable
    (``val()``); the caller treats that as "abandon the fast path"."""
    vals = []
    for v in candidates:
        fm.set_val(v)
        if all(bool(int(c.e.val())) for c in cons_list):
            vals.append(v)
    return vals


class _Walker:
    """Per-instance cyclic walk of one randc field's feasible value list. Serves a
    shuffled sample-without-replacement; a fresh permutation is (re)built by the
    orchestration at each cycle boundary (so the expensive feasible-domain
    computation runs once per cycle, not once per draw)."""

    __slots__ = ("perm", "pos")

    def __init__(self):
        self.perm = None
        self.pos = 0

    def exhausted(self):
        return self.perm is None or self.pos >= len(self.perm)

    def rebuild(self, feasible, randstate):
        perm = list(feasible)
        for i in range(len(perm) - 1, 0, -1):         # Fisher-Yates (seeded)
            j = randstate.randint(0, i)
            perm[i], perm[j] = perm[j], perm[i]
        self.perm = perm
        self.pos = 0

    def next(self):
        v = self.perm[self.pos]
        self.pos += 1
        return v


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def do_randomize_cyclic(obj, tm, randstate, srcinfo, composite, field_models,
                        extra_blocks=None, debug=0, lint=0, solve_fail_debug=0):
    """``Randomizer.do_randomize`` wrapper enforcing ``randc`` cyclic semantics.

    ``extra_blocks`` are caller-supplied constraint blocks (e.g. an inline
    ``randomize_with`` block); they are always applied.
    """
    names = enabled_randc_names(obj, tm)
    base = list(extra_blocks) if extra_blocks else []

    if not names:
        Randomizer.do_randomize(
            randstate, srcinfo, [composite], base or None,
            debug=debug, lint=lint, solve_fail_debug=solve_fail_debug)
        return

    def _exclusion_solve(names_):
        """Value-exclusion cyclic solve over ``names_`` (the always-correct path)."""
        used = getattr(obj, "_vsc_randc_used", None)
        if used is None:
            used = {}
            object.__setattr__(obj, "_vsc_randc_used", used)
        _reset_exhausted(tm, used)
        rc_block = _build_block(tm, used, field_models, names_)
        blocks = base + ([rc_block] if rc_block is not None else [])
        try:
            Randomizer.do_randomize(
                randstate, srcinfo, [composite], blocks or None,
                debug=debug, lint=lint, solve_fail_debug=solve_fail_debug)
        except SolveFailure:
            if rc_block is None:
                raise   # base constraints UNSAT on their own; not a cycle wrap
            for n in names_:
                used[n] = set()
            Randomizer.do_randomize(
                randstate, srcinfo, [composite], base or None,
                debug=debug, lint=lint, solve_fail_debug=solve_fail_debug)
        _record(used, field_models, names_)

    # Fast path is all-or-nothing: every randc field must be separable and
    # constrained only by atomic (evaluable) expressions. Scalar fields take their
    # candidate domain from bound propagation; enum fields from their member set.
    idx = tm.field_index
    name2fm = {n: field_models[n] for n in names if n in field_models}
    if len(name2fm) != len(names):
        _exclusion_solve(names)
        return
    fast, cons = _fast_analysis(names, name2fm, _all_blocks(composite) + base)
    if fast != set(names):
        _exclusion_solve(names)
        return

    walks = getattr(obj, "_vsc_randc_walk", None)
    if walks is None:
        walks = {}
        object.__setattr__(obj, "_vsc_randc_walk", walks)

    # Assign each separable randc its next permutation value as a fixed input.
    # The feasible domain (bound propagation + evaluation filter) is recomputed only
    # when a walker is exhausted -- i.e. once per cycle, not per draw. Any snag
    # (over-cap candidate, empty domain, non-evaluable constraint) reverts the whole
    # object to the exclusion path.
    restores = []   # (fm, saved_val, saved_rand_mode)
    try:
        need_domain = any(
            walks.get(n) is None or walks[n].exhausted() for n in names)
        # Bound propagation is only needed to bound the scalar fields' domains.
        needs_bounds = need_domain and any(
            tm.fields[idx[n]].enum_cls is None for n in names)
        bound_m = _bounds(composite, base) if needs_bounds else None
        for n in names:
            fm = name2fm[n]
            restores.append((fm, int(fm.get_val()), fm.rand_mode))
            w = walks.get(n)
            if w is None or w.exhausted():
                if tm.fields[idx[n]].enum_cls is not None:
                    # Enum: candidate domain is the member set (already the valid
                    # solver-domain values); no bound propagation needed.
                    candidates = list(fm.enums)
                else:
                    bnd = bound_m.get(fm)
                    ranges, size = (_candidate_ranges(bnd)
                                    if bnd is not None else (None, 0))
                    if not ranges or size == 0 or size > _MAX_FAST_DOMAIN:
                        raise _FastBail()
                    candidates = _range_values(ranges)
                feasible = _feasible_values(fm, candidates, cons[n])
                if not feasible:
                    raise _FastBail()
                if w is None:
                    w = _Walker()
                    walks[n] = w
                w.rebuild(feasible, randstate)
            fm.set_val(w.next())
            fm.rand_mode = False
    except Exception:
        for fm, val, rm in restores:
            fm.set_val(val)
            fm.rand_mode = rm
        for n in names:
            walks.pop(n, None)
        _exclusion_solve(names)
        return

    try:
        Randomizer.do_randomize(
            randstate, srcinfo, [composite], base or None,
            debug=debug, lint=lint, solve_fail_debug=solve_fail_debug)
    except SolveFailure:
        # A separable randc's fixed value should never make the rest UNSAT; if it
        # does, our separability/domain was wrong -> revert and use exclusion.
        for fm, val, rm in restores:
            fm.set_val(val)
            fm.rand_mode = rm
        for n in names:
            walks.pop(n, None)
        _exclusion_solve(names)


class _FastBail(Exception):
    """Internal: abandon the fast path and use the exclusion fallback."""
