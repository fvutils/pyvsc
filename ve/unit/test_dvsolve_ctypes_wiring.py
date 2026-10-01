"""Regression: every dv-solve C entry point the Python builder wrapper calls must
have its ctypes ``argtypes`` declared.

An *unwired* function (``argtypes is None``) makes ctypes coerce the 64-bit
``SolveProblemBuilder *`` argument as a C ``int``, **truncating the pointer to 32
bits**. That is harmless only while the builder happens to sit at a low heap
address; at a high address — which AddressSanitizer's allocator and the CI
environment both produce — the truncated pointer is wild and the next field read
(``b->virtual_used`` in ``builder_alloc``) segfaults. This is exactly how an
unwired ``builder_expr_concat`` crashed CI in ``test_dvsolve_fallback_histogram``
on the >64-bit-constant path (``_wide_const`` → ``expr_concat``), while every
local run passed.

This test catches that whole class at import — cheaply, with no ASAN build — by
checking that every ``self._lib.<fn>(...)`` the builder wrapper invokes has
``argtypes`` set, and that each ``builder_*`` entry's first (pointer) argument is
declared ``c_void_p``. It is deliberately source-derived (parses the wrapper) so
a newly-added-but-unwired call is flagged automatically. See
``ve/run_asan.sh`` for the ASAN harness that surfaces the runtime crash.
"""
import ctypes
import re
import unittest
from pathlib import Path

try:
    from dv_solve.lib import _load_lib
    import dv_solve.builder as _builder_mod
    _LIB = _load_lib()
except Exception:               # dv-solve not installed (e.g. the boolector leg)
    _LIB = None
    _builder_mod = None


def _called_c_functions():
    """The set of C entry points invoked as ``self._lib.<name>(`` in the builder
    wrapper — the exact ABI surface that must be wired."""
    src = Path(_builder_mod.__file__).read_text()
    return sorted(set(re.findall(r"self\._lib\.(\w+)\s*\(", src)))


@unittest.skipIf(_LIB is None, "dv-solve native library not available")
class TestDvSolveCtypesWiring(unittest.TestCase):

    def test_all_called_functions_have_argtypes(self):
        # An unwired function truncates the builder pointer -> CI/ASAN crash.
        unwired = [name for name in _called_c_functions()
                   if getattr(_LIB, name).argtypes is None]
        self.assertEqual(
            unwired, [],
            "dv-solve C functions called by builder.py with no ctypes argtypes "
            "(ctypes will truncate the 64-bit builder pointer -> segfault under a "
            "high-address heap / ASAN / CI): %s" % unwired)

    def test_builder_pointer_arg_is_void_p(self):
        # Every builder_* entry takes SolveProblemBuilder* first; it must be
        # c_void_p (a 64-bit pointer), never the default 32-bit int.
        bad = []
        for name in _called_c_functions():
            if not name.startswith("builder_"):
                continue
            argtypes = getattr(_LIB, name).argtypes
            if not argtypes or argtypes[0] is not ctypes.c_void_p:
                bad.append(name)
        self.assertEqual(
            bad, [],
            "builder_* functions whose first (pointer) arg is not c_void_p "
            "(pointer truncation risk): %s" % bad)

    def test_concat_wired_canary(self):
        # Named canary for the exact CI regression: builder_expr_concat unwired.
        fn = getattr(_LIB, "builder_expr_concat")
        self.assertIsNotNone(
            fn.argtypes, "builder_expr_concat lost its ctypes argtypes wiring")
        self.assertIs(fn.argtypes[0], ctypes.c_void_p)


if __name__ == "__main__":
    unittest.main()
