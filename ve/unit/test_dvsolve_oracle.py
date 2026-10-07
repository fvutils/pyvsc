"""The dv-solve oracle check from pyvsc (vsc.set_solver_oracle).

With the oracle on, every dv-solve context pyvsc builds is checked by z3: each
model must satisfy the constraints as z3 reads them, and each UNSAT must be one
z3 agrees with. These randomizations are ones dv-solve gets right, so every
query must come back ok; the run directory is the same format the
dv-solve-smt2 oracle writes, so the dv_solve.oracle report tool reads it.

Skipped when the dv-solve library has no oracle (too old) or z3 is missing.
See packages/dv-solve/docs/api_oracle_plan.md.
"""
import json
import os
import shutil
import tempfile
import unittest

import vsc
from vsc.impl import ctor
from vsc.model.solver.backend import select_backend
from vsc.model.solve_failure import SolveFailure
from vsc_test_case import VscTestCase


def _oracle_available():
    try:
        if not select_backend("dv-solve").available():
            return False
        from dv_solve.lib import _load_lib
        return hasattr(_load_lib(), "dvs_oracle_create") and shutil.which("z3")
    except Exception:
        return False


@vsc.randobj
class Packet(object):
    def __init__(s):
        s.addr = vsc.rand_bit_t(32)
        s.len = vsc.rand_uint8_t()
        s.kind = vsc.rand_bit_t(3)
        s.offs = vsc.rand_int16_t()
        s.data = vsc.rand_list_t(vsc.uint8_t(), 4)

    @vsc.constraint
    def c(s):
        s.addr & 0x3 == 0
        s.addr + s.len < 0x1_0000_0000
        s.len in vsc.rangelist(4, 8, (16, 32))
        vsc.solve_order(s.kind, s.len)
        with vsc.if_then(s.kind == 0):
            s.len == 4
        with vsc.else_then:
            s.len > 4
        s.offs < -10
        vsc.unique(s.data)


@vsc.randobj
class Infeasible(object):
    def __init__(s):
        s.x = vsc.rand_uint8_t()
        s.y = vsc.rand_uint8_t()

    @vsc.constraint
    def c(s):
        s.x < s.y
        s.y < s.x


@unittest.skipUnless(_oracle_available(), "dv-solve oracle or z3 not available")
class TestDvSolveOracle(VscTestCase):

    def setUp(self):
        super().setUp()
        ctor.set_solver_backend("dv-solve")
        self.tmp = tempfile.mkdtemp(prefix="vsc_oracle_")

    def tearDown(self):
        vsc.set_solver_oracle(False)
        ctor.set_solver_backend(None)
        shutil.rmtree(self.tmp, ignore_errors=True)
        super().tearDown()

    def _records(self, run_dir):
        with open(os.path.join(run_dir, "queries.jsonl")) as f:
            return [json.loads(l) for l in f]

    def test_randomize_checked(self):
        o = vsc.set_solver_oracle(out_dir=os.path.join(self.tmp, "run"),
                                  tag="pyvsc-unit", raise_on_fail=True)
        self.assertIs(vsc.get_solver_oracle(), o)
        p = Packet()
        for _ in range(20):
            p.randomize()
            self.assertEqual(int(p.addr) & 3, 0)
        with vsc.randomize_with(p):
            p.len == 16
        run = o.run_dir
        st = o.stats()
        vsc.set_solver_oracle(False)
        self.assertIsNone(vsc.get_solver_oracle())

        recs = self._records(run)
        self.assertGreater(len(recs), 0)
        checked = [r for r in recs if r["res"] != "skipped"]
        self.assertTrue(checked)
        self.assertEqual({r["res"] for r in checked}, {"ok"}, recs)
        self.assertEqual(st["bad_model"] + st["bad_unsat"], 0)
        # Each context is labelled with the fields it randomizes.
        self.assertTrue(any("addr" in (r.get("label") or "") for r in recs))
        with open(os.path.join(run, "run.json")) as f:
            rj = json.load(f)
        self.assertEqual(rj["status"], "complete")
        self.assertEqual(rj["mode"], "api")

    def test_unsat_agrees(self):
        o = vsc.set_solver_oracle(out_dir=os.path.join(self.tmp, "run"),
                                  raise_on_fail=True)
        with self.assertRaises(SolveFailure):
            Infeasible().randomize()
        run = o.run_dir
        vsc.set_solver_oracle(False)
        recs = self._records(run)
        unsat = [r for r in recs if r["dvs"]["verdict"] == "unsat"]
        self.assertTrue(unsat)
        self.assertTrue(all(r["res"] == "ok" for r in unsat), recs)


if __name__ == "__main__":
    unittest.main()
