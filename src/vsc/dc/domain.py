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

"""Declared domains: ``vdc.rand(domain=...)`` as a property of the *variable*.

A declared domain is **not** a constraint. It is folded into the field's initial
bound (``VariableBoundScalarModel``), which is what every consumer downstream
already reads: the dv-solve back-end's ``add_var``/gap re-assertion, the
unconstrained direct-draw path, the Boolector swizzler, and cyclic's candidate
enumeration. Keeping it out of ``constraint_l`` is what lets a domain-only field
stay *separable* -- the precondition for the no-solver T0 tier (plan §4, Phase 2).
Before this, ``solve_view._domain_block`` desugared ``domain=(lo,hi)`` into a pair
of ``ConstraintExprModel`` inequalities, which made every domain-carrying field
look constrained and dragged it into a solve it never needed.

Accepted spellings (all inclusive except ``range``, which keeps Python's
half-open meaning -- the same split documented for ``x in range(...)`` versus
``x in vdc.r[lo:hi]`` in the constraint parser)::

    domain=(3, 250)                  # inclusive [3, 250]
    domain=range(3, 250)             # half-open  [3, 249]
    domain=[1, 2, (100, 200)]        # union: {1, 2} | [100, 200]
    domain=[range(0, 8), (64, 71)]   # union of ranges
    domain=vdc.rangelist(1, rng(4, 9))
    domain={0: 10, range(1, 4): 80, 4: 10}   # weighted (see below)

**Weighted domains** record per-interval weights. Phase 1 only *carries* them;
``solve_view`` still lowers a weighted domain through the existing ``dist``
machinery so semantics are right from day one, and Phase 5 moves them onto the
fast draw. ``weights`` is ``None`` for the (overwhelmingly common) plain case,
and that is the case the T0 tier accepts.
"""

from typing import List, Optional


def _const_of(em, what):
    """Pull a Python int out of a vsc expression model (``rng``/``rangelist``
    endpoints arrive as ``ExprLiteralModel``). Declared-domain endpoints must be
    compile-time constants -- a rand-field endpoint is a *constraint*, not a
    domain, and has to be written as one."""
    val = getattr(em, "val", None)
    if callable(val):
        try:
            return int(val())
        except Exception:
            pass
    if isinstance(em, int):
        return int(em)
    raise TypeError(
        "domain=%s: range endpoints must be compile-time constants (got %r). "
        "A domain bounded by another field is a constraint -- write it as one."
        % (what, em))


def _intervals_of(item, what):
    """Normalize one domain *item* to a list of inclusive ``[lo, hi]`` pairs."""
    # Import here: vsc.types pulls in the expression machinery, and vsc.dc is
    # imported from inside it during package init.
    from vsc.types import rangelist, rng

    if isinstance(item, bool):
        # bool is an int subclass; a True/False domain is almost certainly a typo.
        raise TypeError("domain=%s: bool is not a valid domain element" % (what,))
    if isinstance(item, int):
        return [[item, item]]
    if isinstance(item, range):
        if item.step != 1:
            raise TypeError(
                "domain=%s: range() with a step is not supported in a domain"
                % (what,))
        if len(item) == 0:
            raise TypeError("domain=%s: empty range()" % (what,))
        # Python's range is half-open; the interval list is inclusive.
        return [[item.start, item.stop - 1]]
    if isinstance(item, tuple):
        if len(item) != 2:
            raise TypeError(
                "domain=%s: a tuple domain element must be (lo, hi); got %d "
                "elements" % (what, len(item)))
        return [[_const_of(item[0], what), _const_of(item[1], what)]]
    if isinstance(item, rng):
        return [[_const_of(item.low, what), _const_of(item.high, what)]]
    if isinstance(item, rangelist):
        out = []
        for r in item.range_l.rl:
            lhs, rhs = getattr(r, "lhs", None), getattr(r, "rhs", None)
            if lhs is not None and rhs is not None:
                out.append([_const_of(lhs, what), _const_of(rhs, what)])
            else:
                v = _const_of(r, what)
                out.append([v, v])
        return out
    if isinstance(item, list):
        out = []
        for sub in item:
            out.extend(_intervals_of(sub, what))
        return out
    raise TypeError(
        "domain=%s: unsupported domain element %r. Use an int, (lo, hi), "
        "range(lo, hi), rng(lo, hi), rangelist(...), a list of those, or a "
        "{value_or_range: weight} dict." % (what, item))


def _compact(ranges):
    """Sort and merge overlapping/adjacent intervals."""
    if not ranges:
        return []
    ranges = sorted(ranges, key=lambda r: (r[0], r[1]))
    out = [list(ranges[0])]
    for lo, hi in ranges[1:]:
        if lo <= out[-1][1] + 1:
            if hi > out[-1][1]:
                out[-1][1] = hi
        else:
            out.append([lo, hi])
    return out


class DeclaredDomain(object):
    """A normalized, sorted, disjoint interval list, optionally weighted.

    ``ranges`` is a list of inclusive ``[lo, hi]`` pairs. ``weights``, when not
    ``None``, is a parallel list of positive ints -- one per interval, in the
    same order -- and in that case the intervals are *not* merged (merging would
    destroy the weight assignment), only checked for overlap.
    """

    __slots__ = ("ranges", "weights")

    def __init__(self, ranges: List[List[int]], weights: Optional[List[int]] = None):
        self.ranges = ranges
        self.weights = weights

    @property
    def is_weighted(self):
        return self.weights is not None

    @property
    def size(self):
        """Number of distinct values in the domain."""
        return sum(hi - lo + 1 for lo, hi in self.ranges)

    @property
    def bounds(self):
        """The enclosing ``(lo, hi)`` of the whole domain."""
        return self.ranges[0][0], self.ranges[-1][1]

    @classmethod
    def parse(cls, spec, what="<domain>"):
        """Normalize a user ``domain=`` spec. Returns ``None`` for ``None`` (so
        callers can stay branch-free) and raises ``TypeError`` with an actionable
        message otherwise. Already-normalized input passes through unchanged."""
        if spec is None:
            return None
        if isinstance(spec, DeclaredDomain):
            return spec

        if isinstance(spec, dict):
            ranges, weights = [], []
            for key, w in spec.items():
                w = int(w)
                if w <= 0:
                    raise TypeError(
                        "domain=%s: weight for %r must be positive, got %d"
                        % (what, key, w))
                ivs = _intervals_of(key, what)
                for iv in ivs:
                    # A key spanning several intervals splits its weight across
                    # them proportionally would be surprising; require one
                    # interval per weighted key instead.
                    if len(ivs) != 1:
                        raise TypeError(
                            "domain=%s: a weighted key must be a single value or "
                            "range; %r covers %d intervals"
                            % (what, key, len(ivs)))
                    ranges.append(iv)
                    weights.append(w)
            if not ranges:
                raise TypeError("domain=%s: empty weighted domain" % (what,))
            order = sorted(range(len(ranges)), key=lambda i: ranges[i][0])
            ranges = [ranges[i] for i in order]
            weights = [weights[i] for i in order]
            for i in range(1, len(ranges)):
                if ranges[i][0] <= ranges[i - 1][1]:
                    raise TypeError(
                        "domain=%s: weighted domain entries must not overlap "
                        "(%r and %r)" % (what, ranges[i - 1], ranges[i]))
            for lo, hi in ranges:
                if lo > hi:
                    raise TypeError(
                        "domain=%s: empty interval [%d, %d]" % (what, lo, hi))
            return cls(ranges, weights)

        ranges = _intervals_of(spec, what)
        for lo, hi in ranges:
            if lo > hi:
                raise TypeError(
                    "domain=%s: empty interval [%d, %d] (lo must be <= hi)"
                    % (what, lo, hi))
        if not ranges:
            raise TypeError("domain=%s: empty domain" % (what,))
        return cls(_compact(ranges), None)

    def __eq__(self, other):
        return (isinstance(other, DeclaredDomain)
                and self.ranges == other.ranges
                and self.weights == other.weights)

    def __repr__(self):
        if self.weights is None:
            return "DeclaredDomain(%r)" % (self.ranges,)
        return "DeclaredDomain(%r, weights=%r)" % (self.ranges, self.weights)


def intersect(a: List[List[int]], b: List[List[int]]) -> List[List[int]]:
    """Intersect two sorted, disjoint inclusive-interval lists.

    This is the *interaction rule* (plan §4, Phase 1.3): a declared domain
    intersects with the field's width range and with whatever constraints also
    reference the field. Declaring a domain never widens a field and never
    overrides a constraint; an empty result is a normal UNSAT, reported by the
    usual empty-bound path rather than silently producing a value.
    """
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
