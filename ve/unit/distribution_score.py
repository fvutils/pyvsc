'''
Quantitative distribution-quality scoring for randomization back-ends.

Binary pass/fail ("was every value hit?") doesn't say *how* uniform a back-end's
output is, nor let us compare back-ends. This module scores a sample with two
interpretable metrics:

  * **uniformity** — a chi-square goodness-of-fit test against the uniform
    distribution over the feasible values. Reported as the *reduced* chi-square
    ``chi2/dof`` (≈ 1.0 for a perfectly uniform source, growing as the
    distribution skews) and a p-value (probability of seeing a deviation this
    large from a truly uniform source; p > ~0.01 is "consistent with uniform").

  * **coverage** — the fraction of feasible values actually observed, plus the
    coupon-collector ratio ``n_samples / (V·ln V)`` (a uniform source needs
    ≈ V·ln V samples to cover all V values; ratio ≥ ~1 should give full
    coverage).

Pure-Python (no scipy): the chi-square survival function uses the regularized
upper incomplete gamma function.

@author: solver-backend integration
'''
import math


# ------------------------------------------------------------------ #
# Regularized incomplete gamma  →  chi-square survival function        #
# ------------------------------------------------------------------ #

def _gamma_p_series(s, x):
    """Regularized lower incomplete gamma P(s,x) via series (good for x < s+1)."""
    if x <= 0.0:
        return 0.0
    ap = s
    total = 1.0 / s
    term = total
    for _ in range(1000):
        ap += 1.0
        term *= x / ap
        total += term
        if abs(term) < abs(total) * 1e-15:
            break
    return total * math.exp(-x + s * math.log(x) - math.lgamma(s))


def _gamma_q_cf(s, x):
    """Regularized upper incomplete gamma Q(s,x) via continued fraction
    (good for x >= s+1)."""
    tiny = 1e-300
    b = x + 1.0 - s
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, 1000):
        an = -i * (i - s)
        b += 2.0
        d = an * d + b
        if abs(d) < tiny:
            d = tiny
        c = b + an / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return math.exp(-x + s * math.log(x) - math.lgamma(s)) * h


def _gamma_q(s, x):
    """Regularized upper incomplete gamma Q(s,x) = 1 - P(s,x)."""
    if x < 0.0 or s <= 0.0:
        return 1.0
    if x < s + 1.0:
        return 1.0 - _gamma_p_series(s, x)
    return _gamma_q_cf(s, x)


def chi2_sf(chi2, dof):
    """Chi-square survival function: P(X > chi2) for X ~ chi-square(dof).
    This is the p-value of the goodness-of-fit test."""
    if dof <= 0:
        return 1.0
    return _gamma_q(dof / 2.0, chi2 / 2.0)


# ------------------------------------------------------------------ #
# Scoring                                                              #
# ------------------------------------------------------------------ #

class DistScore(object):
    def __init__(self, n_samples, feasible, observed):
        self.n_samples = n_samples
        self.n_feasible = len(feasible)          # V: number of feasible values
        self.n_distinct = sum(1 for v in feasible if observed.get(v, 0) > 0)
        self.coverage = self.n_distinct / self.n_feasible if self.n_feasible else 1.0

        # Chi-square vs uniform over the feasible values.
        expected = n_samples / self.n_feasible if self.n_feasible else 0.0
        if expected > 0 and self.n_feasible > 1:
            chi2 = 0.0
            for v in feasible:
                o = observed.get(v, 0)
                chi2 += (o - expected) ** 2 / expected
            self.chi2 = chi2
            self.dof = self.n_feasible - 1
            self.reduced_chi2 = chi2 / self.dof
            self.p_value = chi2_sf(chi2, self.dof)
        else:
            self.chi2 = 0.0
            self.dof = 0
            self.reduced_chi2 = 1.0
            self.p_value = 1.0

        # Coupon-collector ratio: samples / (V ln V) — ≥ ~1 expected for full
        # coverage from a uniform source.
        v = self.n_feasible
        self.coupon_ratio = (n_samples / (v * math.log(v))) if v > 1 else float("inf")

    def __str__(self):
        return ("reduced_chi2=%6.2f  p=%.3g  coverage=%5.1f%% (%d/%d)  coupon_x=%.2f"
                % (self.reduced_chi2, self.p_value, 100 * self.coverage,
                   self.n_distinct, self.n_feasible, self.coupon_ratio))


def score(values, feasible):
    """Score an iterable of sampled ``values`` against the list of ``feasible``
    values (the legal domain). Returns a DistScore."""
    observed = {}
    n = 0
    for v in values:
        v = int(v)
        observed[v] = observed.get(v, 0) + 1
        n += 1
    return DistScore(n, list(feasible), observed)
