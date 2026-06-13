"""T-E4b — libdv_solve auto-loads from its installed package location.

Regression lock for Phase E / E4-2. The native library must load **without**
any env override (`ZSP_SOLVER_PATH` / `LD_LIBRARY_PATH`): `dv_solve.lib`
searches build directories relative to its own location. The original bug walked
up *four* parents from `lib.py` (landing at `packages/`, which never contains the
build dir) so the lib only loaded when an env var pointed at it; the fix walks up
*three* (to `packages/dv-solve/`, the real package root). This test pins that:
with both env vars unset, `_find_library()` must resolve a `.so` under the
package root and `_load_lib()` must return a live handle.

Skips when the lib was not built in-place under the package root (e.g. a CI host
that built it into a /tmp pytest dir) — there is no package-location load to
verify there, and the conformance matrix covers the env-pointed path.

Runnable standalone: ``python ve/unit/test_dvsolve_lib_load.py``.
"""
import importlib
import os
import unittest
from pathlib import Path


def _dv_solve_lib():
    try:
        return importlib.import_module("dv_solve.lib")
    except Exception:
        return None


def _package_build_dirs(lib_mod):
    """The build dirs `_candidate_paths` derives from lib.py's own location.

    Mirrors `_candidate_paths` candidate group #3: pkg_root is three parents up
    from lib.py (dv_solve/ -> src/ -> dv-solve/). This is the exact level the
    E4-2 fix corrected (was four, which overshot to packages/).
    """
    pkg_root = Path(lib_mod.__file__).parent.parent.parent
    names = ("build", "_build", "build_release", "cmake-build-release")
    return [pkg_root / n for n in names]


def _has_package_built_lib(lib_mod):
    for d in _package_build_dirs(lib_mod):
        if d.is_dir() and any(d.glob("libdv_solve.so*")):
            return True
    return False


_LIB_MOD = _dv_solve_lib()


@unittest.skipUnless(_LIB_MOD is not None, "dv_solve package not importable")
@unittest.skipUnless(
    _LIB_MOD is not None and _has_package_built_lib(_LIB_MOD),
    "libdv_solve.so not built in-place under the package root",
)
class TestDvSolveLibLoad(unittest.TestCase):

    def setUp(self):
        self.lib = _LIB_MOD
        # Snapshot the env vars and the module-level load cache so each test
        # runs a *fresh* search and we leave global state untouched afterward.
        self._saved_env = {
            k: os.environ.get(k)
            for k in ("ZSP_SOLVER_PATH", "LD_LIBRARY_PATH")
        }
        self._saved_cache = self.lib._LIB_CACHE
        self._saved_attempted = self.lib._LOAD_ATTEMPTED

    def tearDown(self):
        for k, v in self._saved_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.lib._LIB_CACHE = self._saved_cache
        self.lib._LOAD_ATTEMPTED = self._saved_attempted

    def _clear_env_and_cache(self):
        os.environ.pop("ZSP_SOLVER_PATH", None)
        os.environ.pop("LD_LIBRARY_PATH", None)
        self.lib._LIB_CACHE = None
        self.lib._LOAD_ATTEMPTED = False

    def test_find_library_resolves_to_package_location(self):
        """With no env override, the search lands in the package build dir."""
        self._clear_env_and_cache()

        found = self.lib._find_library()
        self.assertIsNotNone(
            found,
            "lib not found with ZSP_SOLVER_PATH/LD_LIBRARY_PATH unset — the "
            "package-relative build-dir search (E4-2) regressed",
        )

        build_dirs = {d.resolve() for d in _package_build_dirs(self.lib)}
        self.assertIn(
            found.parent.resolve(), build_dirs,
            "lib resolved from %s, not a package build dir %s — pkg_root walks "
            "the wrong number of parents (E4-2)" % (found.parent, build_dirs),
        )

    def test_load_lib_succeeds_without_env(self):
        """_load_lib returns a live handle with both env vars unset."""
        self._clear_env_and_cache()

        lib = self.lib._load_lib()
        self.assertIsNotNone(
            lib, "libdv_solve failed to load without an env override (E4-2)")
        # A real, wired handle: a known export must be present.
        self.assertTrue(hasattr(lib, "solve_problem_init"))


if __name__ == "__main__":
    unittest.main()
