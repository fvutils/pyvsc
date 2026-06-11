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

# Created on Jun 9, 2026
#
# Boolector solver back-end. This is the historical pyvsc solve loop relocated
# behind SolverBackendIF; behavior is identical to the pre-refactor inline
# block in Randomizer.randomize (see git history / design §4.2).

from typing import Dict

from vsc.model.solver.backend import SolverBackendIF, SolveResult
from vsc.model.solve_failure import SolveFailure
from vsc.model.rand_set_node_builder import RandSetNodeBuilder
from vsc.model.solvegroup_swizzler_partsel import SolveGroupSwizzlerPartsel
from vsc.visitors.model_pretty_printer import ModelPrettyPrinter


class BoolectorBackend(SolverBackendIF):
    """Wraps the existing Boolector machinery (RandSetNodeBuilder, the node
    ``build(btor)`` methods, and the partsel swizzler). Solving and value
    read-back are exactly as before the back-end refactor."""

    name = "boolector"
    supports_soft = True
    supports_dist_native = False
    # Boolector returns a single fixed model; the swizzler supplies the spread.
    randomizes_internally = False

    @classmethod
    def available(cls) -> bool:
        try:
            import pyboolector  # noqa: F401
            return True
        except ImportError:
            return False

    def solve_randset(self,
                      rs,
                      bound_m: Dict,
                      randstate,
                      solve_info=None,
                      debug=0) -> SolveResult:
        # Imported lazily so that merely importing this module does not require
        # pyboolector to be present (selection guards on available()).
        import pyboolector
        from pyboolector import Boolector

        pretty_printer = ModelPrettyPrinter()

        btor = Boolector()
        btor.Set_opt(pyboolector.BtorOption.BTOR_OPT_INCREMENTAL, True)
        btor.Set_opt(pyboolector.BtorOption.BTOR_OPT_MODEL_GEN, True)

        rs_node_builder = RandSetNodeBuilder(btor)
        rs_node_builder.build(rs)

        constraint_l = list(map(lambda c: (c, c.build(btor, False)), rs.constraints()))
        soft_constraint_l = list(map(lambda c: (c, c.build(btor, True)), rs.soft_constraints()))

        # Sort the list in descending order so we know which constraints
        # to prioritize
        soft_constraint_l.sort(key=lambda c: c[0].priority, reverse=True)

        for c in constraint_l:
            try:
                btor.Assume(c[1])
            except Exception as e:
                print("Exception: " + pretty_printer.print(c[0]))
                raise e

        if solve_info is not None:
            solve_info.n_sat_calls += 1

        if btor.Sat() != btor.SAT:
            # If the system doesn't solve with hard constraints added, then we
            # may as well bail now. The Randomizer handles disposal and
            # diagnostics for the SolveFailure.
            raise SolveFailure(
                "solve failure",
                "Solve failure: set 'solve_fail_debug=1' for more details")
        else:
            # Lock down the hard constraints that are confirmed to be valid
            for c in constraint_l:
                btor.Assert(c[1])

        # If there are soft constraints, add these now
        if len(soft_constraint_l) > 0:
            for c in soft_constraint_l:
                try:
                    btor.Assume(c[1])
                except Exception as e:
                    print("Exception: " + ModelPrettyPrinter.print(c[0]))
                    raise e

            if solve_info is not None:
                solve_info.n_sat_calls += 1
            if btor.Sat() != btor.SAT:
                # All the soft constraints cannot be satisfied. We'll need to
                # add them incrementally
                if debug > 0:
                    print("Note: some of the %d soft constraints could not be satisfied" % len(soft_constraint_l))

                for c in soft_constraint_l:
                    btor.Assume(c[1])

                    if solve_info is not None:
                        solve_info.n_sat_calls += 1
                    if btor.Sat() == btor.SAT:
                        if debug > 0:
                            print("Note: soft constraint %s (%d) passed" % (
                                pretty_printer.print(c[0]), c[0].priority))
                        btor.Assert(c[1])
                    else:
                        if debug > 0:
                            print("Note: soft constraint %s (%d) failed" % (
                                pretty_printer.print(c[0]), c[0].priority))
            else:
                # All the soft constraints could be satisfied. Assert them now
                if debug > 0:
                    print("Note: all %d soft constraints could be satisfied" % len(soft_constraint_l))
                for c in soft_constraint_l:
                    btor.Assert(c[1])

        # Spread the solution across the legal space
        swizzler = SolveGroupSwizzlerPartsel(randstate, solve_info, debug=debug)
        swizzler.swizzle(btor, rs, bound_m)

        # Values now live in each field's Boolector var. The Randomizer's
        # finalize loop reads them via post_randomize() and disposes the vars.
        return SolveResult(status=0)
