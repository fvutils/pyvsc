"""
Free-function API mirroring the methods on :class:`RandClass`, so users can write
``vdc.randomize(obj)`` as well as ``obj.randomize()`` (parity with ``vsc.randomize``).
"""
from .rand_class import RandClass


def randomize(obj, debug=0, lint=0, solve_fail_debug=0):
    if not isinstance(obj, RandClass):
        raise TypeError("vdc.randomize() expects a vdc.RandClass instance, got %s"
                        % type(obj).__name__)
    return obj.randomize(debug=debug, lint=lint, solve_fail_debug=solve_fail_debug)


def randomize_with(obj, debug=0, lint=0, solve_fail_debug=0):
    if not isinstance(obj, RandClass):
        raise TypeError("vdc.randomize_with() expects a vdc.RandClass instance, got %s"
                        % type(obj).__name__)
    return obj.randomize_with(debug=debug, lint=lint, solve_fail_debug=solve_fail_debug)
