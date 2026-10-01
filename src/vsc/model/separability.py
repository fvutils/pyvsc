# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

"""Separability analysis, shared by two consumers.

*Separable* means a rand field never co-occurs with another rand field inside a
single constraint statement, so its value can be chosen on its own without
consulting a solver.

Consumer 1 -- ``vsc.dc.cyclic``: the ``randc`` fast path, which needs the
feasible value *list* of each separable field so it can walk it cyclically.
It tolerates a conservative (superset) domain because it filters candidates by
evaluation afterwards.

Consumer 2 -- the **T0 tier** (``t0_promote``): promotes an entire RandSet out
of the solver and into the unconstrained direct-draw path. That has no
after-the-fact filter, so its domain must be **exact**, and it is computed here
from the constraint expressions themselves rather than from bound propagation:

  * propagated bounds are only guaranteed to be a *superset* (they exist to
    drive the swizzler, where over-approximating is harmless), and
  * on a back-end that derives bounds natively the propagation pass is skipped
    entirely (``declared_only=True``), so ``bound_m`` carries no constraint
    information at all.

So T0's analysis is deliberately narrow: an expression it does not recognize
makes the RandSet ineligible, and it falls back to the solver. Everything it
*does* recognize it computes exactly, as an inclusive interval set.
"""

from vsc.model.bin_expr_type import BinExprType
from vsc.model.constraint_expr_model import ConstraintExprModel
from vsc.model.expr_bin_model import ExprBinModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.expr_in_model import ExprInModel
from vsc.model.expr_literal_model import ExprLiteralModel
from vsc.model.expr_range_model import ExprRangeModel
from vsc.model.field_scalar_model import FieldScalarModel
from vsc.model.model_visitor import ModelVisitor
from vsc.model.variable_bound_model import VariableBoundModel


# ---------------------------------------------------------------------------
# Rand-reference collection
# ---------------------------------------------------------------------------

class _RandRefCollector(ModelVisitor):
    """Collect the rand field models referenced by a constraint statement.

    ``pred`` decides what counts as "rand". The two consumers disagree slightly:
    cyclic asks for *declared* rand with ``rand_mode`` on (it runs before
    ``set_used_rand``), T0 asks for ``is_used_rand`` (it runs after).
    """

    def __init__(self, pred):
        super().__init__()
        self.pred = pred
        self.refs = set()

    def visit_expr_fieldref(self, e):
        if self.pred(e.fm):
            self.refs.add(e.fm)


def _declared_rand(fm):
    return (getattr(fm, "is_declared_rand", False)
            and getattr(fm, "rand_mode", False))


def _used_rand(fm):
    return getattr(fm, "is_used_rand", False)


def rand_refs(stmt, pred=_declared_rand):
    c = _RandRefCollector(pred)
    stmt.accept(c)
    return c.refs


def analyze_separable(targets, stmts, pred=_declared_rand):
    """Decide separability and collect atomic constraints for each target field.

    ``targets`` is an iterable of FieldModel, ``stmts`` an iterable of
    constraint statements. Returns ``(separable, cons)``: ``separable`` is the
    subset of ``targets`` that never co-occurs with another rand field in a
    statement and whose every referencing statement is an atomic
    ``ConstraintExprModel``; ``cons`` maps every target to the list of atomic
    constraints referencing it.
    """
    target_s = set(targets)
    ok = set(target_s)
    cons = {f: [] for f in target_s}
    for stmt in stmts:
        refs = rand_refs(stmt, pred)
        here = [fm for fm in refs if fm in target_s]
        if not here:
            continue
        if len(refs) > 1:                     # coupled to another rand field
            for f in here:
                ok.discard(f)
        if isinstance(stmt, ConstraintExprModel):
            for f in here:
                cons[f].append(stmt)
        else:                                 # non-atomic (scope/foreach/...)
            for f in here:
                ok.discard(f)
    return ok, cons


# ---------------------------------------------------------------------------
# Exact interval-set arithmetic (inclusive, sorted, disjoint, merged)
# ---------------------------------------------------------------------------

def _compact(ranges):
    out = []
    for lo, hi in sorted(ranges):
        if lo > hi:
            continue
        if out and lo <= out[-1][1] + 1:
            if hi > out[-1][1]:
                out[-1][1] = hi
        else:
            out.append([lo, hi])
    return out


def _intersect(a, b):
    out = []
    i = j = 0
    while i < len(a) and j < len(b):
        lo = max(a[i][0], b[j][0])
        hi = min(a[i][1], b[j][1])
        if lo <= hi:
            out.append([lo, hi])
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def _union(a, b):
    return _compact([list(r) for r in a] + [list(r) for r in b])


def _complement(ranges, lo, hi):
    out = []
    pos = lo
    for r_lo, r_hi in ranges:
        if r_lo > pos:
            out.append([pos, r_lo - 1])
        pos = max(pos, r_hi + 1)
    if pos <= hi:
        out.append([pos, hi])
    return out


def width_ranges(f):
    """The field's value range from its width and signedness, intersected with
    its declared domain (``vdc.rand(domain=...)``). This is the same rule
    VariableBoundScalarModel applies -- both are properties of the *variable*,
    which is exactly why T0 can reproduce them without the solver."""
    if f.is_signed:
        base = [[-(1 << (f.width - 1)), (1 << (f.width - 1)) - 1]]
    else:
        base = [[0, (1 << f.width) - 1]]
    dd = getattr(f, "declared_domain", None)
    if dd is None:
        return base
    return _intersect([list(r) for r in dd.ranges], base)


# ---------------------------------------------------------------------------
# Exact per-field domain from a constraint expression
# ---------------------------------------------------------------------------

_CMP_OPS = (BinExprType.Eq, BinExprType.Ne, BinExprType.Gt,
            BinExprType.Ge, BinExprType.Lt, BinExprType.Le)

# Comparison with the operands swapped: `k < f` is `f > k`.
_FLIP = {
    BinExprType.Eq: BinExprType.Eq,
    BinExprType.Ne: BinExprType.Ne,
    BinExprType.Gt: BinExprType.Lt,
    BinExprType.Ge: BinExprType.Le,
    BinExprType.Lt: BinExprType.Gt,
    BinExprType.Le: BinExprType.Ge,
}


def _const(e):
    """Int value of ``e`` if it is constant for this solve, else None.

    A reference to a non-rand field counts: its value is fixed before the solve
    starts (the config/knob pattern). The plan cache tracks exactly those
    fields' values in its freshness signature, so a cached T0 domain is
    invalidated when one of them changes.
    """
    if isinstance(e, ExprLiteralModel):
        return int(e.val())
    if isinstance(e, ExprFieldRefModel):
        fm = e.fm
        if isinstance(fm, FieldScalarModel) and not fm.is_used_rand:
            return int(fm.get_val())
    return None


def _is_ref(e, f):
    return isinstance(e, ExprFieldRefModel) and e.fm is f


def _cmp_ranges(op, k, lo, hi):
    if op is BinExprType.Lt:
        return _intersect([[lo, hi]], [[lo, k - 1]]) if k - 1 >= lo else []
    if op is BinExprType.Le:
        return _intersect([[lo, hi]], [[lo, k]]) if k >= lo else []
    if op is BinExprType.Gt:
        return _intersect([[lo, hi]], [[k + 1, hi]]) if k + 1 <= hi else []
    if op is BinExprType.Ge:
        return _intersect([[lo, hi]], [[k, hi]]) if k <= hi else []
    if op is BinExprType.Eq:
        return [[k, k]] if lo <= k <= hi else []
    if op is BinExprType.Ne:
        return _complement([[k, k]] if lo <= k <= hi else [], lo, hi)
    return None


def expr_ranges(e, f, lo, hi):
    """Exact set of values of ``f`` in ``[lo,hi]`` satisfying ``e``, or None if
    the expression is not one this analysis handles.

    Signed/unsigned comparison semantics are not an issue here: every result is
    intersected with the field's own ``[lo,hi]`` range, over which Python's
    integer comparison agrees with the solver's sized comparison.
    """
    if isinstance(e, ExprBinModel):
        op = e.op
        if op is BinExprType.And:
            a = expr_ranges(e.lhs, f, lo, hi)
            if a is None:
                return None
            b = expr_ranges(e.rhs, f, lo, hi)
            if b is None:
                return None
            return _intersect(a, b)
        if op is BinExprType.Or:
            a = expr_ranges(e.lhs, f, lo, hi)
            if a is None:
                return None
            b = expr_ranges(e.rhs, f, lo, hi)
            if b is None:
                return None
            return _union(a, b)
        if op in _CMP_OPS:
            if _is_ref(e.lhs, f):
                k = _const(e.rhs)
                if k is not None:
                    return _cmp_ranges(op, k, lo, hi)
            if _is_ref(e.rhs, f):
                k = _const(e.lhs)
                if k is not None:
                    return _cmp_ranges(_FLIP[op], k, lo, hi)
        return None
    if isinstance(e, ExprInModel):
        if not _is_ref(e.lhs, f):
            return None
        out = []
        for r in e.rhs.rl:
            if isinstance(r, ExprRangeModel):
                r_lo, r_hi = _const(r.lhs), _const(r.rhs)
                if r_lo is None or r_hi is None:
                    return None
                out.append([r_lo, r_hi])
            else:
                k = _const(r)
                if k is None:
                    return None            # e.g. an array membership term
                out.append([k, k])
        return _intersect(_compact(out), [[lo, hi]])
    return None


# ---------------------------------------------------------------------------
# T0 eligibility
# ---------------------------------------------------------------------------

def _t0_field_ok(f):
    # Exact type: a subclass (EnumFieldModel) takes its domain from its member
    # set rather than its width, and an array/composite is not a direct draw.
    if type(f) is not FieldScalarModel:
        return False
    # The unconstrained draw does not call post_randomize, so a field with a
    # rand_if would lose its callback. Requiring None is what makes promotion
    # observationally identical to the solver path (a scalar with var=None and
    # rand_if=None has a no-op post_randomize).
    if f.rand_if is not None:
        return False
    # The `size` field of a variable-size array drives array expansion; drawing
    # it directly would set a length nothing acts on.
    if getattr(f.parent, "size", None) is f:
        return False
    return True


def analyze_randset(rs):
    """Exact per-field domains if this RandSet is T0-eligible, else None.

    Returns a list of ``(field, ranges)`` in RandSet field order (order matters:
    it fixes the sequence of draws, and so random stability).
    """
    if rs.soft_constraints():
        return None
    if getattr(rs, "dist_field_m", None):
        return None
    if getattr(rs, "rand_order_l", None) is not None:
        return None

    rand_l = [f for f in rs.rand_fields() if f.is_used_rand]
    if not rand_l:
        return None
    for f in rand_l:
        if not _t0_field_ok(f):
            return None
    rand_s = set(rand_l)

    dom = {f: width_ranges(f) for f in rand_l}

    for stmt in rs.constraints():
        if not isinstance(stmt, ConstraintExprModel):
            return None
        refs = rand_refs(stmt, _used_rand)
        # Exactly one rand field per statement: that *is* separability, and it
        # is also the precondition for the single-variable interval analysis
        # below. A statement over zero rand fields is a constant assertion that
        # only the solver can report on.
        if len(refs) != 1:
            return None
        f = next(iter(refs))
        if f not in rand_s:
            return None
        cur = dom[f]
        r = expr_ranges(stmt.e, f, cur[0][0], cur[-1][1]) if cur else []
        if r is None:
            return None
        dom[f] = _intersect(cur, r)

    for f in rand_l:
        if not dom[f]:
            # Genuinely UNSAT. Defer to the solver so the failure is reported
            # through the normal diagnostics path rather than from here.
            return None

    return [(f, dom[f]) for f in rand_l]


def t0_promote(ri):
    """Move every T0-eligible RandSet into ``ri.unconstrained_l``.

    Returns a dict of ``field -> VariableBoundModel`` carrying the exact domain
    for each promoted field; the caller installs them into ``bound_m``, which is
    what the direct-draw loop reads. The promoted RandSets are retained on
    ``ri.t0_randset_l`` so the plan cache still sees the fields and constraints
    they reference when it builds its freshness signature.
    """
    keep = []
    promoted = []
    bounds = {}
    for rs in ri.randset_l:
        dom = analyze_randset(rs)
        if dom is None:
            keep.append(rs)
            continue
        promoted.append(rs)
        for f, ranges in dom:
            bm = VariableBoundModel(f)
            for lo, hi in ranges:
                bm.domain.add_range(lo, hi)
            bm.constrained = True
            bounds[f] = bm
            ri.unconstrained_l.append(f)
    if promoted:
        ri.randset_l = keep
        ri.t0_randset_l = promoted
    return bounds
