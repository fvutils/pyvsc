"""One riscv-dv pygen program, generated in its own process (the riscv-dv suite).

    python3 -P benchmarks/perf/riscv_dv_child.py '<json spec>'   (perf.riscv_dv does this)

The spec names a riscv-dv checkout, a testlist entry, a seed and the arm's
back-end. The child imports pygen against whichever pyvsc its PYTHONPATH holds
and generates one program the way `run.py --simulator pyflow` would (the
testlist's gen_opts, `+` turned into `--`), but in-process: it calls the test's
_run_phase(0) directly instead of going through run.py's subprocess and
pygen's multiprocessing.Pool, so the timed region is generation only.

The pinned upstream riscv-dv is used as published, with two fixes applied
here at import (see _compat): Python 3.12 removed `imp`, and pygen's
get_rand_instr ignores its exclude lists. Both are riscv-dv bugs, not
modelling changes. The port tree (packages/riscv-dv-new) has both fixed in
place, so the spec turns the patches off for it ("fixes": false).

Correctness: an oracle re-checks the solver's answers in plain Python,
reading only field values, so it holds for any front-end and back-end:

- gpr: riscv_rand_instr_stream.randomize_gpr's inline constraints (register
  operands inside the stream's avail_regs, rd off the reserved registers),
  and the stream's avail_regs size against its element count;
- instr: every instruction's own constraints, checked on entry to
  post_randomize (before imm is sign-extended): the shift-amount masks, the
  compressed register sets, the nonzero-immediate and no-hint rules;
- stream: riscv_int_numeric_corner_stream's avail_regs (10, unique, not
  zero, not reserved) and its list sizes and instruction count.

A violation is counted, not raised, so a build that drops those constraints
still produces a measurable program and the count is recorded beside its time.

Prints one JSON object on stdout.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import json
import logging
import os
import random
import re
import sys
import tempfile
import time
import traceback
import types


def _compat():
    """riscv-dv fixes, applied to the imported modules (the tree is untouched)."""
    # pygen_src/isa/riscv_instr.py does `from imp import reload`; imp is gone
    # in Python 3.12.
    if "imp" not in sys.modules:
        imp = types.ModuleType("imp")
        imp.reload = importlib.reload
        sys.modules["imp"] = imp


def _fix_get_rand_instr():
    """pygen's get_rand_instr builds a disallowed list and never applies it,
    so a stream that excludes, say, the compressed groups still gets
    compressed instructions. SV riscv-dv draws from the allowed set minus the
    disallowed set; this does the same. (riscv_int_numeric_corner_stream
    excludes RV32C; without the fix it can draw C.ADDI16SP, whose rd == sp
    contradicts the stream's own avail_regs, and a solver that honours both
    constraints correctly reports the inline randomize as unsatisfiable.)"""
    import copy
    from pygen_src.isa.riscv_instr import riscv_instr

    def get_rand_instr(cls, include_instr=[], exclude_instr=[],
                       include_category=[], exclude_category=[],
                       include_group=[], exclude_group=[]):
        allowed, disallowed = [], set(exclude_instr)
        for c in include_category:
            allowed.extend(cls.instr_category[c])
        for c in exclude_category:
            disallowed.update(cls.instr_category.get(c, []))
        for g in include_group:
            allowed.extend(cls.instr_group[g])
        for g in exclude_group:
            disallowed.update(cls.instr_group.get(g, []))
        pool = include_instr or allowed or cls.instr_names
        pool = [n for n in pool if n not in disallowed and n in cls.instr_names]
        return copy.deepcopy(cls.instr_template[random.choice(pool)])

    riscv_instr.get_rand_instr = classmethod(get_rand_instr)


_C_REGS = range(8, 16)          # s0..a5: the 3-bit register fields of C formats
_C_NARROW = ("CIW_FORMAT", "CL_FORMAT", "CS_FORMAT", "CB_FORMAT", "CA_FORMAT")
_C_NO_ZERO_RD = ("C_ADDI", "C_ADDIW", "C_LI", "C_LUI", "C_SLLI", "C_SLLI64",
                 "C_LQSP", "C_LDSP", "C_MV", "C_ADD", "C_LWSP")
_ZERO, _SP = 0, 2


def _name(v):
    return getattr(v, "name", None) or str(v)


def _bits(v, hi, lo):
    return (v >> lo) & ((1 << (hi - lo + 1)) - 1)


def instr_violations(instr, compressed: bool) -> list:
    """riscv_instr.imm_c and riscv_compressed_instr's constraints, on the
    values the solver chose (imm not yet sign-extended)."""
    name = _name(instr.instr_name)
    fmt = _name(instr.format)
    rs1, rs2, rd = int(instr.rs1), int(instr.rs2), int(instr.rd)
    imm, xlen = int(instr.imm) & 0xFFFFFFFF, int(instr.XLEN)
    bad = []
    if name in ("SLLIW", "SRLIW", "SRAIW") or (name in ("SLLI", "SRLI", "SRAI") and xlen == 32):
        if _bits(imm, 11, 5):
            bad.append("imm[11:5] != 0")
    elif name in ("SLLI", "SRLI", "SRAI") and _bits(imm, 11, 6):
        bad.append("imm[11:6] != 0")
    if not compressed:
        return bad
    if fmt in _C_NARROW:
        for f, v in (("rs1", rs1), ("rs2", rs2), ("rd", rd)):
            if getattr(instr, "has_" + f) and v not in _C_REGS:
                bad.append(f"{f} {v} not in s0..a5")
    if name == "C_ADDI16SP" and rd != _SP:
        bad.append("rd != sp")
    if name in ("C_JR", "C_JALR") and rs1 == _ZERO:
        bad.append("rs1 == zero")
    if _name(instr.imm_type) in ("NZIMM", "NZUIMM"):
        if _bits(imm, 5, 0) == 0:
            bad.append("imm[5:0] == 0")
        if name in ("C_LUI", "C_SRAI", "C_SRLI", "C_SLLI") and _bits(imm, 31, 5):
            bad.append("imm[31:5] != 0")
        if name == "C_ADDI4SPN" and _bits(imm, 1, 0):
            bad.append("imm[1:0] != 0")
    if xlen != 32 and name == "C_JAL":
        bad.append("C_JAL with XLEN != 32")
    if name in _C_NO_ZERO_RD and rd == _ZERO:
        bad.append("rd == zero (hint)")
    if name in ("C_ADD", "C_MV") and rs2 == _ZERO:
        bad.append("rs2 == zero (hint)")
    if name == "C_LUI" and rd == _SP:
        bad.append("rd == sp")
    return bad


def _regs(lst):
    """A register list's values, and whether its size disagrees with its
    elements. Classic pyvsc lists are read through their model: the elements
    the program appended, and separately the size pyvsc holds for them. They
    differ when a randomize() of another object overwrote this unrandomized
    list's size (pyvsc <= 0.9.6), which also breaks len() and iteration."""
    if hasattr(lst, "get_model"):
        m = lst.get_model()
        return [int(f.get_val()) for f in m.field_l], int(m.size.get_val()) != len(m.field_l)
    return [int(x) for x in lst], False


class _Oracle:
    """Re-checks the solver's answers in plain Python (see the module doc)."""

    KINDS = ("gpr", "instr", "stream")

    def __init__(self):
        self.calls = 0
        self.violations = 0
        self.by_kind = dict.fromkeys(self.KINDS, 0)
        self.corrupt = 0
        self.first = None

    def _bad(self, kind, what, bad):
        if bad:
            self.violations += 1
            self.by_kind[kind] += 1
            if self.first is None:
                self.first = f"{kind}: {what}: " + "; ".join(bad)

    def install(self):
        from pygen_src import riscv_instr_stream as m
        from pygen_src.isa.riscv_instr import riscv_instr
        from pygen_src.riscv_instr_gen_config import cfg
        from pygen_src.riscv_instr_pkg import riscv_instr_format_t
        cb = int(riscv_instr_format_t.CB_FORMAT)
        oracle = self

        orig_gpr = m.riscv_rand_instr_stream.randomize_gpr

        def randomize_gpr(stream, instr):
            out = orig_gpr(stream, instr)
            oracle.check_gpr(stream, out, cfg, cb)
            return out
        m.riscv_rand_instr_stream.randomize_gpr = randomize_gpr

        try:
            from pygen_src.isa.riscv_compressed_instr import riscv_compressed_instr
        except ImportError:
            riscv_compressed_instr = ()
        orig_post = riscv_instr.post_randomize

        def post_randomize(instr):
            oracle.calls += 1
            oracle._bad("instr", _name(instr.instr_name),
                        instr_violations(instr, isinstance(instr, riscv_compressed_instr)))
            return orig_post(instr)
        riscv_instr.post_randomize = post_randomize

        from pygen_src import riscv_directed_instr_lib as d
        corner = d.riscv_int_numeric_corner_stream
        orig_corner = corner.post_randomize

        def corner_post(stream):
            oracle.check_corner(stream, cfg)
            return orig_corner(stream)
        corner.post_randomize = corner_post

    def check_gpr(self, stream, instr, cfg, cb):
        avail, corrupt = _regs(stream.avail_regs)
        self.corrupt += corrupt
        bad = []
        ops = (("rs1", instr.has_rs1), ("rs2", instr.has_rs2), ("rd", instr.has_rd))
        if avail:
            bad += [f"{n} {int(getattr(instr, n))} not in avail_regs"
                    for n, has in ops if has and int(getattr(instr, n)) not in avail]
        for r in [int(x) for x in stream.reserved_rd] + [int(x) for x in cfg.reserved_regs]:
            if instr.has_rd and int(instr.rd) == r:
                bad.append(f"rd {r} is reserved")
            if int(instr.format) == cb and int(instr.rs1) == r:
                bad.append(f"rs1 {r} is reserved (CB format)")
        self._bad("gpr", _name(instr.instr_name), bad)

    def check_corner(self, stream, cfg):
        avail, _ = _regs(stream.avail_regs)
        reserved = {int(x) for x in cfg.reserved_regs}
        bad = []
        if len(avail) != 10 or len(set(avail)) != len(avail):
            bad.append(f"avail_regs {avail} is not 10 unique registers")
        bad += [f"avail_regs holds {r}" for r in avail if r == _ZERO or r in reserved]
        if not 15 <= int(stream.num_of_instr) <= 30:
            bad.append(f"num_of_instr {int(stream.num_of_instr)} not in 15..30")
        for f in ("init_val", "init_val_type"):
            if len(getattr(stream, f)) != 10:
                bad.append(f"len({f}) != 10")
        self._bad("stream", "riscv_int_numeric_corner_stream", bad)


_INSTR = re.compile(r"^\s+[a-z][a-z0-9.]*(\s|$)")


def count_instructions(asm: str) -> int:
    """Instruction lines in a generated .S: indented, not a directive or label."""
    n = 0
    for line in asm.splitlines():
        if _INSTR.match(line) and not line.strip().endswith(":"):
            n += 1
    return n


def gen_args(rdv: str, spec: dict, out: str) -> tuple:
    """(argv, gen_test) as run.py's pyflow path builds them for this test."""
    import yaml
    entries = yaml.safe_load(open(os.path.join(rdv, "yaml", "base_testlist.yaml")))
    ent = [e for e in entries if isinstance(e, dict) and e.get("test") == spec["test"]]
    if not ent:
        raise LookupError(f"{spec['test']} is not in riscv-dv's base testlist")
    ent = ent[0]
    opts = [re.sub(r"^\+", "--", o) for o in (ent.get("gen_opts") or "").split()]
    if spec.get("instr_cnt"):
        opts = [o for o in opts if not o.startswith("--instr_cnt=")]
        opts.append(f"--instr_cnt={spec['instr_cnt']}")
    # gen_test=none keeps the base test module from running itself at import.
    argv = ["pygen", "--num_of_tests=1", "--start_idx=0", f"--asm_file_name={out}",
            f"--target={spec.get('target', 'rv32imc')}", "--gen_test=none",
            f"--seed={spec['seed']}"] + opts
    return argv, ent["gen_test"]


def measure(spec: dict) -> dict:
    rdv = spec["rdv"]
    res = {"status": "ok"}
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "prog")
        argv, gen_test = gen_args(rdv, spec, out)
        os.chdir(rdv)
        sys.path.insert(0, os.path.join(rdv, "pygen"))
        sys.argv = argv
        fixes = spec.get("fixes", True)
        if fixes:
            _compat()

        import vsc
        res["versions"] = {"vsc_file": vsc.__file__}
        try:
            from importlib.metadata import version
            res["versions"]["pyboolector"] = version("pyboolector")
        except Exception:
            res["versions"]["pyboolector"] = None
        if spec.get("backend"):
            vsc.set_solver_backend(spec["backend"])
            if spec["backend"] == "dv-solve":
                import dv_solve
                res["versions"]["dv_solve"] = getattr(dv_solve, "__version__", None)
                res["versions"]["dv_solve_file"] = dv_solve.__file__
        from vsc.model.randomizer import Randomizer
        tally = None
        try:
            from vsc.model import randomizer as rz
            rz.set_fallback_tally(True)
            rz.reset_fallback_tally()
            tally = rz.get_fallback_tally
        except (ImportError, AttributeError):
            pass

        calls = [0]
        inner = Randomizer.do_randomize

        def do_randomize(*a, **k):
            calls[0] += 1
            return inner(*a, **k)
        Randomizer.do_randomize = staticmethod(do_randomize)

        logging.disable(logging.CRITICAL)
        with contextlib.redirect_stdout(io.StringIO()):
            from pygen_src.test.riscv_instr_base_test import riscv_instr_base_test
            cls = riscv_instr_base_test
            if gen_test != "riscv_instr_base_test":
                # These modules run their test at import; take the class only.
                path = os.path.join(rdv, "pygen", "pygen_src", "test", gen_test + ".py")
                src = open(path).read().split("start_time = time.time()")[0]
                ns = {"__name__": "rdv_" + gen_test}
                exec(compile(src, path, "exec"), ns)
                cls = ns[gen_test]
            if fixes:
                _fix_get_rand_instr()
            oracle = _Oracle()
            oracle.install()
            test = cls()

            c0, w0 = time.process_time(), time.perf_counter()
            test._run_phase(0)
            cpu, wall = time.process_time() - c0, time.perf_counter() - w0
        asm = open(out + "_0.S").read()

    n = count_instructions(asm)
    res.update(cpu_s=round(cpu, 3), wall_s=round(wall, 3), instrs=n,
               randomize_calls=calls[0], asm_sha=hashlib.sha256(asm.encode()).hexdigest()[:16],
               checked=oracle.calls, violations=oracle.violations,
               violations_by=oracle.by_kind,
               corrupt_size=oracle.corrupt,
               fallback=tally() if tally else None)
    if oracle.first:
        res["first_violation"] = oracle.first
    return res


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    spec = json.loads(argv[0])
    if spec.get("cpu") is not None:
        os.sched_setaffinity(0, {spec["cpu"]})
    real_stdout = sys.stdout
    try:
        res = measure(spec)
    except Exception as e:
        res = {"status": "error", "error": f"{type(e).__name__}: {e}",
               "trace": traceback.format_exc()[-1500:]}
    real_stdout.write("\n" + json.dumps(res) + "\n")
    real_stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
