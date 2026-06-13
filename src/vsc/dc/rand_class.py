"""
``vdc.RandClass`` — the random capability base class for the dataclass front-end.

Provides real, inherited ``randomize()`` / ``randomize_with()`` methods (good IDE
and ``isinstance`` behavior), backed by a per-type :class:`TypeModel` and pyvsc's
existing ``Randomizer`` / ``dv-solve`` back-end.

(Renamed from the design's ``RandObj`` per review — see plan §0.)
"""
import sys

from vsc.model.rand_state import RandState
from vsc.model.randomizer import Randomizer
from vsc.model.solve_failure import SolveFailure
from vsc.model.source_info import SourceInfo

from . import solve_view
from .type_model import build_type_model


class RandClass:
    """Inherit to make a ``@vdc.dataclass`` randomizable."""

    def _get_type_model(self):
        cls = type(self)
        tm = cls.__dict__.get("_vsc_type_model")
        if tm is None:
            # Self-bootstrap if the decorator was skipped or this is a bare subclass.
            tm = build_type_model(cls)
            cls._vsc_type_model = tm
        return tm

    def _get_randstate(self):
        rs = getattr(self, "_vsc_randstate", None)
        if rs is None:
            rs = RandState.mk()
            object.__setattr__(self, "_vsc_randstate", rs)
        return rs

    def get_randstate(self):
        return self._get_randstate().clone()

    def set_randstate(self, rs):
        object.__setattr__(self, "_vsc_randstate", rs.clone())

    # -- rand_mode ---------------------------------------------------------
    # Dataclass fields are plain values, so rand_mode is controlled through a
    # method rather than the classic ``it.a.rand_mode = False`` attribute (which
    # required vsc.raw_mode()). A disabled field holds its current value across
    # randomize() instead of being solved for.

    def set_rand_mode(self, name, enabled):
        tm = self._get_type_model()
        if name not in tm.field_index:
            raise AttributeError("no field %r on %s" % (name, type(self).__name__))
        rm = getattr(self, "_vsc_rand_mode", None)
        if rm is None:
            rm = {}
            object.__setattr__(self, "_vsc_rand_mode", rm)
        rm[name] = bool(enabled)

    def get_rand_mode(self, name):
        tm = self._get_type_model()
        fd = tm.fields[tm.field_index[name]]
        rm = getattr(self, "_vsc_rand_mode", None)
        if rm is not None and name in rm:
            return rm[name]
        return fd.is_rand   # default: declared-rand fields are rand-enabled

    def randomize(self, debug=0, lint=0, solve_fail_debug=0):
        tm = self._get_type_model()
        frame = sys._getframe(1)
        composite, field_models = solve_view.get_solve_model(self, tm)
        # Writeback + user post_randomize run inside do_randomize via the model's
        # rand_if (so post_randomize sees solved values and its edits stick).
        Randomizer.do_randomize(
            self._get_randstate(),
            SourceInfo(frame.f_code.co_filename, frame.f_lineno),
            [composite],
            debug=debug, lint=lint, solve_fail_debug=solve_fail_debug)

    def randomize_with(self, debug=0, lint=0, solve_fail_debug=0):
        # Imported lazily to avoid a module import cycle (inline -> solve_view).
        from .inline import RandomizeWith
        return RandomizeWith(self, debug=debug, lint=lint,
                             solve_fail_debug=solve_fail_debug)
