"""Minimal deterministic SVG charts for the results pages.

Hand-written rather than matplotlib, as in dv-solve's tests/perf/svg.py
(whose frame and legend this follows): the output is byte-stable for the
same data, and the docs build gains no dependency.
"""
from __future__ import annotations

import math
from html import escape

W, H = 760, 400
ML, MR, MT, MB = 64, 150, 20, 64          # margins; legend sits in the right one
PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#8c564b", "#17becf"]


def _fmt(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".") if v < 10 else f"{v:,.0f}"


def _log_ticks(lo: float, hi: float) -> list:
    """Decades, plus 2 and 5 between them when the range is narrow."""
    out = []
    span = math.log10(hi / lo)
    mults = (1, 2, 5) if span <= 3 else (1,)
    e = math.floor(math.log10(lo))
    while 10 ** e <= hi * 1.0001:
        for m in mults:
            t = m * 10 ** e
            if lo * 0.9999 <= t <= hi * 1.0001:
                out.append(t)
        e += 1
    return out


def _frame(title_x: str, title_y: str, xticks: list, yticks: list) -> list:
    pw, ph = W - ML - MR, H - MT - MB
    s = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
         f'font-family="sans-serif" font-size="12" role="img">',
         f'<rect x="0" y="0" width="{W}" height="{H}" fill="#ffffff"/>',
         f'<rect x="{ML}" y="{MT}" width="{pw}" height="{ph}" fill="none" stroke="#999"/>']
    for x, lab in xticks:
        s.append(f'<line x1="{x:.1f}" y1="{MT}" x2="{x:.1f}" y2="{MT + ph}" stroke="#eee"/>')
        for k, part in enumerate(lab.split("\n")):
            s.append(f'<text x="{x:.1f}" y="{MT + ph + 16 + 14 * k}" text-anchor="middle">'
                     f'{escape(part)}</text>')
    for y, lab in yticks:
        s.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{ML + pw}" y2="{y:.1f}" stroke="#eee"/>')
        s.append(f'<text x="{ML - 6}" y="{y + 4:.1f}" text-anchor="end">{escape(lab)}</text>')
    s.append(f'<text x="{ML + pw / 2}" y="{H - 8}" text-anchor="middle">{escape(title_x)}</text>')
    s.append(f'<text transform="translate(14,{MT + ph / 2}) rotate(-90)" text-anchor="middle">'
             f'{escape(title_y)}</text>')
    return s


def _legend(names: list) -> list:
    s, x = [], W - MR + 14
    for i, n in enumerate(names):
        y = MT + 10 + 18 * i
        c = PALETTE[i % len(PALETTE)]
        s.append(f'<line x1="{x}" y1="{y}" x2="{x + 18}" y2="{y}" stroke="{c}" stroke-width="2.5"/>')
        s.append(f'<text x="{x + 24}" y="{y + 4}">{escape(n)}</text>')
    return s


def trend(labels: list, series: dict, title_y: str, hollow: set = frozenset(),
          breaks: set = frozenset(), title_x: str = "") -> str:
    """One line per series over evenly spaced runs, log y.

    labels: one x label per run (may hold a newline); series: {name: [value or
    None per run]}; hollow: indices of runs drawn with open markers (noisy,
    dirty or invalid); breaks: indices where a new segment starts (the suite
    changed, so the values before aren't comparable), drawn as a dashed
    vertical line. A None also breaks the line."""
    vals = [v for vs in series.values() for v in vs if v]
    if not vals or not labels:
        return ""
    lo = min(vals) / 1.25
    hi = max(vals) * 1.25
    pw, ph = W - ML - MR, H - MT - MB
    n = len(labels)
    X = lambda i: ML + pw * (i + 0.5) / n                                 # noqa: E731
    Y = lambda v: MT + ph - ph * (math.log10(v) - math.log10(lo)) / (math.log10(hi) - math.log10(lo))  # noqa: E731,E501
    every = max(1, math.ceil(n / 8))                  # at most ~8 x labels
    shown = list(range(0, n, every))
    if shown[-1] != n - 1:                            # always label the newest run,
        if n - 1 - shown[-1] < every:                 # dropping a neighbour it would hit
            shown.pop()
        shown.append(n - 1)
    xt = [(X(i), labels[i]) for i in shown]
    yt = [(Y(t), _fmt(t)) for t in _log_ticks(lo, hi)]
    s = _frame(title_x, title_y, xt, yt)
    for i in sorted(breaks):
        bx = (X(i - 1) + X(i)) / 2
        s.append(f'<line x1="{bx:.1f}" y1="{MT}" x2="{bx:.1f}" y2="{MT + ph}" stroke="#888" '
                 f'stroke-dasharray="4 3"/>')
    for k, (name, vs) in enumerate(series.items()):
        c = PALETTE[k % len(PALETTE)]
        d, pen = [], "M"
        for i, v in enumerate(vs):
            if i in breaks:
                pen = "M"
            if v:
                d.append(f"{pen}{X(i):.1f},{Y(v):.1f}")
                pen = "L"
            else:
                pen = "M"
        if len(d) > 1:
            s.append(f'<path d="{"".join(d)}" fill="none" stroke="{c}" stroke-width="2"/>')
        for i, v in enumerate(vs):
            if v:
                fill = "#ffffff" if i in hollow else c
                s.append(f'<circle cx="{X(i):.1f}" cy="{Y(v):.1f}" r="3.8" fill="{fill}" '
                         f'stroke="{c}" stroke-width="1.6"><title>{escape(name)}: '
                         f'{_fmt(v)}</title></circle>')
    s += _legend(list(series))
    s.append("</svg>")
    return "\n".join(s) + "\n"
