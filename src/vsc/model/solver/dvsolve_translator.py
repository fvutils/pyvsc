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
# Translates a pyvsc constraint/expression AST into dv-solve ExprRefs (plan
# P1-2, design §4.3/§5). The pyvsc model nodes are read through the
# ModelVisitor interface and are NOT modified; their build(btor) methods are
# untouched.
#
# Empirical findings backing the mapping (validated against libdv_solve.so):
#   * dv-solve auto-reconciles mixed operand widths, so no manual expr_extend
#     is needed for Phase-1 arithmetic.
#   * Comparison signedness is carried on the variable declaration, so the
#     translator emits the same op for signed/unsigned operands.
#   * Boolean combination of width-1 comparison results via BIN_BAND/BIN_BOR
#     is equivalent to logical and/or (matches the Boolector path, which uses
#     bitwise And/Or on width-1 nodes).

from vsc.model.model_visitor import ModelVisitor
from vsc.model.bin_expr_type import BinExprType
from vsc.model.unary_expr_type import UnaryExprType
from vsc.model.expr_range_model import ExprRangeModel
from vsc.model.expr_fieldref_model import ExprFieldRefModel
from vsc.model.field_array_model import FieldArrayModel
from vsc.model.solver.backend import BackendIncomplete

from dv_solve.problem import (
    BIN_ADD, BIN_SUB, BIN_MUL, BIN_DIV, BIN_MOD,
    BIN_BAND, BIN_BOR, BIN_BXOR, BIN_LSHIFT, BIN_RSHIFT,
    BIN_EQ, BIN_NEQ, BIN_LT, BIN_LTE, BIN_GT, BIN_GTE,
    BIN_AND, BIN_OR,
    UN_NOT, UN_INVERT,
)


# pyvsc BinExprType -> dv-solve BIN_* opcode (design §5).
#
# IMPORTANT: dv-solve distinguishes *logical* and/or (BIN_AND/BIN_OR) from
# *bitwise* and/or (BIN_BAND/BIN_BOR). The native compiler only recognizes the
# logical forms as boolean structure (conjunction/disjunction of constraints);
# the bitwise forms are arithmetic. pyvsc's BinExprType.And/Or are overloaded
# for both, distinguished by width (a width-1 result is boolean), so they are
# resolved in visit_expr_bin rather than via this table.
_BIN_OP = {
    BinExprType.Eq:  BIN_EQ,
    BinExprType.Ne:  BIN_NEQ,
    BinExprType.Gt:  BIN_GT,
    BinExprType.Ge:  BIN_GTE,
    BinExprType.Lt:  BIN_LT,
    BinExprType.Le:  BIN_LTE,
    BinExprType.Add: BIN_ADD,
    BinExprType.Sub: BIN_SUB,
    BinExprType.Mul: BIN_MUL,
    BinExprType.Div: BIN_DIV,
    BinExprType.Mod: BIN_MOD,
    BinExprType.Xor: BIN_BXOR,
    BinExprType.Sll: BIN_LSHIFT,
    BinExprType.Srl: BIN_RSHIFT,
}


_COMPARISON_OPS = frozenset((
    BinExprType.Eq, BinExprType.Ne,
    BinExprType.Gt, BinExprType.Ge, BinExprType.Lt, BinExprType.Le,
))

# Relational (ordering) comparisons — the native compiler reifies these only
# over plain var/const operands, so an arithmetic operand must be materialized.
# Equality (Eq/Ne) is handled separately: `var == <op>` compiles directly.
_RELATIONAL_OPS = frozenset((
    BinExprType.Gt, BinExprType.Ge, BinExprType.Lt, BinExprType.Le,
))


# Sentinel marking "this visit produced no result" so an unhandled node is
# detected rather than silently returning a stale ExprRef.
_UNSET = object()


class DvSolveExprTranslator(ModelVisitor):
    """ModelVisitor that returns dv-solve ExprRef ints via ``translate(node)``.

    Each ``translate`` returns the ExprRef for a (sub)expression or constraint.
    Constraint nodes translate to a boolean (0/1) ExprRef suitable as a root
    for ``add_constraint``. Any unsupported construct raises ``BackendIncomplete``
    so the Randomizer can fall back to another back-end.
    """

    def __init__(self, builder, idmap):
        super().__init__()
        self._b = builder
        self._m = idmap
        self._result = _UNSET
        # Context width flowing top-down, mirroring ExprBinModel.build(ctx_width):
        # an arithmetic result is materialized at the *context* width (max of the
        # enclosing operands), not its bottom-up width, so wrap matches Boolector
        # (e.g. d16 == a8+b8 evaluates the sum at 16 bits — no wrap).
        self._ctx_width = -1
        # Memo of already-translated (node, ctx_width) -> ExprRef. Expression
        # trees can be DAGs (shared sub-expressions); without memoization a
        # shared node is re-translated at every occurrence, and because each
        # arithmetic node materializes a fresh aux var, that re-expansion is
        # exponential in the sharing depth (a runaway that can exhaust memory).
        # The result of translating a node depends only on its context width, so
        # caching by (id(node), ctx_width) is sound for one solve *provided the
        # nodes stay alive* — see _keepalive below.
        self._memo = {}
        # The memo key uses id(node). Some nodes are synthesized during
        # translation (e.g. visit_expr_in builds a fresh ExprBin tree) and would
        # otherwise be garbage-collected immediately, letting a later synthetic
        # node reuse the same address → a stale memo hit that silently grafts one
        # expression onto another. Holding a reference to every translated node
        # for the duration of the solve keeps ids unique and the memo correct.
        self._keepalive = []
        # want_var: does the consumer need this result to be a plain variable
        # (vs accepting a raw value-op)? The native compiler compiles
        # `var == <single op>` and `var CMP var/const` directly, so an arithmetic
        # op only needs to be lifted into an aux variable when it is itself an
        # operand of another value-op or a *relational* comparison. Materializing
        # only then (instead of always) avoids an extra aux var + constraint +
        # propagator per arithmetic op — the bulk of the Phase-2 slowdown.
        self._want_var = False
        # Set by each visit: True iff its result is a plain var/const ref.
        self._last_simple = False
        # Non-rand fields referenced as constants, with their value at build
        # time. The backend uses this to invalidate a cached compiled problem
        # when a referenced non-rand field's value changes (the value is baked
        # into the problem as an expr_const).
        self.const_fields = {}

    def translate(self, node, ctx_width=-1, want_var=False) -> int:
        """Walk ``node`` at the given context width; return its dv-solve ExprRef.

        ``want_var`` forces a value-op result into an aux variable (see
        ``_want_var``). Also sets ``self._last_simple`` for the caller.
        """
        self._keepalive.append(node)
        key = (id(node), ctx_width, want_var)
        cached = self._memo.get(key, _UNSET)
        if cached is not _UNSET:
            self._last_simple = cached[1]
            return cached[0]
        saved_ctx = self._ctx_width
        saved_wv = self._want_var
        saved_res = self._result
        self._ctx_width = ctx_width
        self._want_var = want_var
        self._result = _UNSET
        self._last_simple = False
        node.accept(self)
        r = self._result
        simple = self._last_simple
        self._ctx_width = saved_ctx
        self._want_var = saved_wv
        self._result = saved_res
        if r is _UNSET:
            raise BackendIncomplete(
                "dv-solve translator does not handle node %s" % type(node).__name__)
        self._memo[key] = (r, simple)
        self._last_simple = simple
        return r

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _ref_for_field(self, fm) -> int:
        """A registered (rand) field becomes a var ref; anything else is a
        constant from its current value (mirrors Boolector's const path for
        non-rand fields)."""
        if self._m.has(fm):
            return self._b.expr_var(self._m.id_of(fm))
        else:
            val = int(fm.val)
            # Record the baked-in constant so a cached compiled problem can be
            # invalidated when this non-rand field's value later changes.
            self.const_fields[fm] = val
            return self._b.expr_const(val, bool(fm.is_signed))

    def _to_bool(self, ref: int, src_expr) -> int:
        """Coerce a value expression to a boolean root, mirroring
        ``ExprModel.toBool``: a width-1 expression is already boolean; anything
        wider becomes ``expr != 0``.

        Reads ``self._last_simple`` (set by the immediately-preceding
        ``translate(src_expr)``): the `!= 0` form needs a plain operand, so a raw
        value-op is materialized first."""
        try:
            w = int(src_expr.width())
        except Exception:
            w = -1
        if w == 1:
            return ref
        if not self._last_simple and self._AUX_MIN_W <= w <= self._AUX_MAX_W:
            try:
                signed = src_expr.is_signed()
            except Exception:
                signed = False
            ref = self._materialize(ref, w, signed)
        return self._b.expr_binary(BIN_NEQ, ref, self._b.expr_const(0))

    # Widths the native modular arithmetic propagators handle. Outside this
    # range we leave the raw expression (and let fallback handle it) rather
    # than materialize an aux var the engine can't reason about soundly.
    _AUX_MIN_W = 1
    _AUX_MAX_W = 63

    def _materialize(self, ref: int, width, is_signed) -> int:
        """Lift a value-producing expression into a fresh auxiliary variable
        constrained to equal it (``aux == ref``), returning the aux's var ref.

        This is the flattening that lets the native compiler handle nested and
        embedded arithmetic: every compound value becomes a plain variable, and
        the compiler already compiles ``aux == <primitive op>`` and
        ``var CMP var/const``. The aux is declared at pyvsc's expression width
        (so the modular propagators wrap bit-accurately) — width information the
        dv-solve IR itself does not carry, which is why this lives here.
        """
        try:
            w = int(width)
        except Exception:
            w = 0
        if w < self._AUX_MIN_W or w > self._AUX_MAX_W:
            # Can't size/wrap an aux soundly; leave the raw expression. If an
            # enclosing context needs a var, compilation reports incomplete and
            # the Randomizer falls back.
            return ref
        signed = bool(is_signed)
        if signed:
            lo = -(1 << (w - 1))
            hi = (1 << (w - 1)) - 1
        else:
            lo = 0
            hi = (1 << w) - 1
        aux = self._m.alloc_aux()
        self._b.add_var(aux, w, signed, lo, hi)
        aux_ref = self._b.expr_var(aux)
        self._b.add_constraint(self._b.expr_binary(BIN_EQ, aux_ref, ref))
        return aux_ref

    def _conj(self, refs) -> int:
        """Logical-AND-combine a list of boolean refs; empty list -> true."""
        result = None
        for r in refs:
            result = r if result is None else self._b.expr_binary(BIN_AND, result, r)
        if result is None:
            result = self._b.expr_const(1)
        return result

    # ------------------------------------------------------------------ #
    # Expression nodes                                                     #
    # ------------------------------------------------------------------ #

    def visit_scalar_field(self, f):
        self._result = self._ref_for_field(f)
        self._last_simple = True

    def visit_enum_field(self, f):
        # Enum membership is enforced at variable-declaration time by the
        # backend; here an enum reference behaves like any scalar field.
        self._result = self._ref_for_field(f)
        self._last_simple = True

    def visit_expr_fieldref(self, e):
        self._result = self._ref_for_field(e.fm)
        self._last_simple = True

    def visit_expr_literal(self, e):
        v = int(e.val())
        signed = bool(e.signed)
        if -(1 << 63) <= v <= (1 << 63) - 1:
            # Fits a signed int64 directly.
            self._result = self._b.expr_const(v, signed)
        else:
            w = int(e.width()) if e.width() else v.bit_length()
            if w <= 64:
                # A 64-bit pattern that overflows signed int64 (e.g. a uint64
                # literal >= 2^63): pass its two's-complement reinterpretation —
                # the same bit pattern, sized to context by the engine.
                self._result = self._b.expr_const(v - (1 << 64), signed)
            else:
                # >64-bit literal can't be a single int64 const node; lower it to
                # a concat of <=64-bit const limbs (Phase D).
                self._result = self._wide_const(v, w)
        self._last_simple = True

    def _wide_const(self, v, w):
        """Lower a >64-bit constant ``v`` of width ``w`` into a concat of
        <=64-bit const limbs (``expr_const`` is int64). limb 0 is the low 64
        bits; the engine's ``concat(hi, lo, lo_width)`` stacks them MSB-first."""
        v &= (1 << w) - 1                      # unsigned bit pattern
        limbs = []                             # (value, width), low -> high
        rem, rest = w, v
        while rem > 0:
            lw = 64 if rem >= 64 else rem
            limbs.append((rest & ((1 << lw) - 1), lw))
            rest >>= lw
            rem -= lw

        def const_limb(limb, lw):
            # Pass the bit pattern; a full 64-bit limb with bit 63 set must go in
            # as its signed reinterpretation (lw<64 limbs are always < 2^63).
            sv = limb - (1 << 64) if (lw == 64 and limb >= (1 << 63)) else limb
            return self._b.expr_const(sv, False)

        acc = const_limb(*limbs[-1])           # highest limb
        for i in range(len(limbs) - 2, -1, -1):
            limb, lw = limbs[i]
            acc = self._b.expr_concat(acc, const_limb(limb, lw), lw)
        return acc

    def visit_expr_bin(self, e):
        is_logical = False
        if e.op in (BinExprType.And, BinExprType.Or):
            # Logical when the result is a single bit (boolean combination of
            # comparisons); bitwise otherwise. Mirrors how the Boolector path
            # uses width-1 And/Or as logical connectives.
            is_logical = (e.width() == 1)
            if e.op == BinExprType.And:
                op = BIN_AND if is_logical else BIN_BAND
            else:
                op = BIN_OR if is_logical else BIN_BOR
        else:
            op = _BIN_OP.get(e.op)
            if op is None:
                raise BackendIncomplete("dv-solve: unsupported binary op %s" % str(e.op))

        # Context width = max(inherited, operand widths) — Boolector's rule. The
        # operands are translated at this width and an arithmetic result is
        # materialized at it, so wrap happens at exactly the same width.
        ctx_width = self._ctx_width
        # Coerce to plain ints: some width() methods (e.g. ExprPartselectModel)
        # return a ValueScalar, which is unhashable and would break the memo key
        # and ctypes width args downstream.
        lhs_w = int(e.lhs.width())
        rhs_w = int(e.rhs.width())
        if lhs_w > ctx_width:
            ctx_width = lhs_w
        if rhs_w > ctx_width:
            ctx_width = rhs_w

        is_relational = e.op in _RELATIONAL_OPS
        is_equality = e.op in (BinExprType.Eq, BinExprType.Ne)

        if is_relational:
            # The compiler reifies `var/const CMP var/const`, so both operands
            # must be plain — materialize any value-op operand.
            lhs = self.translate(e.lhs, ctx_width, want_var=True)
            rhs = self.translate(e.rhs, ctx_width, want_var=True)
            self._result = self._b.expr_binary(op, lhs, rhs)
            self._last_simple = False
        elif is_equality:
            # The compiler handles `var/const == <op>` (one plain side). Keep
            # both operands raw; only if *neither* is plain do we lift one.
            lhs = self.translate(e.lhs, ctx_width)
            lhs_simple = self._last_simple
            rhs = self.translate(e.rhs, ctx_width)
            rhs_simple = self._last_simple
            if not lhs_simple and not rhs_simple:
                rhs = self._materialize(rhs, ctx_width, e.rhs.is_signed())
            self._result = self._b.expr_binary(op, lhs, rhs)
            self._last_simple = False
        elif is_logical:
            # Boolean combination of comparison results.
            lhs = self.translate(e.lhs, ctx_width)
            rhs = self.translate(e.rhs, ctx_width)
            self._result = self._b.expr_binary(op, lhs, rhs)
            self._last_simple = False
        else:
            # Value-producing op (arithmetic / multi-bit bitwise / shift). Its
            # operands must be plain for the native arith propagators; the op
            # itself is lifted into an aux only when its consumer needs a var.
            lhs = self.translate(e.lhs, ctx_width, want_var=True)
            rhs = self.translate(e.rhs, ctx_width, want_var=True)
            ref = self._b.expr_binary(op, lhs, rhs)
            auxable = self._AUX_MIN_W <= ctx_width <= self._AUX_MAX_W
            if self._want_var and auxable:
                self._result = self._materialize(ref, ctx_width, e.is_signed())
                self._last_simple = True
            else:
                # Raw value-op (consumed directly by `var == op`, or width out
                # of aux range → let compile/fallback handle it).
                self._result = ref
                self._last_simple = False

    def visit_expr_unary(self, e):
        if e.op != UnaryExprType.Not:
            raise BackendIncomplete("dv-solve: unsupported unary op %s" % str(e.op))
        # pyvsc's only unary op (`~`) is a *bitwise* invert (the Boolector path
        # uses btor.Not, which complements every bit), so it must map to the
        # bitwise UN_INVERT at the operand's full width — NOT the logical UN_NOT.
        # (For a 1-bit operand — e.g. ~(a == b) — UN_INVERT degenerates to logical
        # negation anyway, so boolean-context uses are unaffected.) Mapping it to
        # UN_NOT made `a == ~b` mean `a == !b`, e.g. a=0 whenever b != 0.
        ctx_width = self._ctx_width
        ew = int(e.expr.width())
        if ew > ctx_width:
            ctx_width = ew
        operand = self.translate(e.expr, ctx_width, want_var=True)
        ref = self._b.expr_unary(UN_INVERT, operand)
        if self._want_var and self._AUX_MIN_W <= ctx_width <= self._AUX_MAX_W:
            self._result = self._materialize(ref, ctx_width, e.is_signed())
            self._last_simple = True
        else:
            self._result = ref
            self._last_simple = False

    def visit_expr_cond(self, e):
        cond = self._to_bool(self.translate(e.cond_e), e.cond_e)
        # ITE arms must be plain for the native ite; raw value-ops there don't
        # compile.
        true_e = self.translate(e.true_e, want_var=True)
        false_e = self.translate(e.false_e, want_var=True)
        ref = self._b.expr_ite(cond, true_e, false_e)
        # ExprCondModel.width() is 0, so size the aux from the context width.
        cw = self._ctx_width
        if self._want_var and self._AUX_MIN_W <= cw <= self._AUX_MAX_W:
            self._result = self._materialize(ref, cw, e.is_signed())
            self._last_simple = True
        else:
            self._result = ref
            self._last_simple = False

    def visit_expr_in(self, e):
        # Mirror ExprInModel.build exactly, but as an ExprModel tree we then
        # translate. Each range becomes (lhs >= lo) && (lhs <= hi); scalar/field
        # entries become equalities; all OR'd together. This reuses visit_expr_bin
        # (so the logical/bitwise width rule applies) and avoids the native
        # expr_in_range, which the compiler does not accept as an OR leaf.
        from vsc.model.expr_bin_model import ExprBinModel
        expr = None
        for r in e.rhs.rl:
            if isinstance(r, ExprRangeModel):
                term = ExprBinModel(
                    ExprBinModel(e.lhs, BinExprType.Ge, r.lhs),
                    BinExprType.And,
                    ExprBinModel(e.lhs, BinExprType.Le, r.rhs))
            elif isinstance(r, ExprFieldRefModel) and isinstance(r.fm, FieldArrayModel):
                # 'in' over an array's elements -- deferred to Phase 2.
                raise BackendIncomplete("dv-solve: 'in' over array not yet supported")
            else:
                term = ExprBinModel(e.lhs, BinExprType.Eq, r)
            expr = term if expr is None else ExprBinModel(expr, BinExprType.Or, term)
        if expr is None:
            self._result = self._b.expr_const(1)
        else:
            self._result = self.translate(expr)

    # ------------------------------------------------------------------ #
    # Constraint nodes (translate to boolean roots)                        #
    # ------------------------------------------------------------------ #

    def visit_constraint_expr(self, c):
        self._result = self._to_bool(self.translate(c.e), c.e)

    def visit_constraint_soft(self, c):
        self._result = self._to_bool(self.translate(c.expr), c.expr)

    def visit_constraint_scope(self, c):
        self._result = self._conj([self.translate(cc) for cc in c.constraint_l])

    def visit_constraint_block(self, c):
        self.visit_constraint_scope(c)

    def visit_constraint_implies(self, c):
        cond = self._to_bool(self.translate(c.cond), c.cond)
        body = self._conj([self.translate(cc) for cc in c.constraint_l])
        # cond -> body  ==  (!cond) || body  (logical OR; the native compiler
        # does not accept a top-level ite as a constraint).
        self._result = self._b.expr_binary(
            BIN_OR, self._b.expr_unary(UN_NOT, cond), body)

    def visit_constraint_if_else(self, c):
        cond = self._to_bool(self.translate(c.cond), c.cond)
        notcond = self._b.expr_unary(UN_NOT, cond)
        true_c = self.translate(c.true_c)
        if c.false_c is None:
            # cond -> true  ==  (!cond) || true
            self._result = self._b.expr_binary(BIN_OR, notcond, true_c)
        else:
            # (cond -> true) && (!cond -> false)
            #   == (!cond || true) && (cond || false)
            false_c = self.translate(c.false_c)
            left = self._b.expr_binary(BIN_OR, notcond, true_c)
            right = self._b.expr_binary(BIN_OR, cond, false_c)
            self._result = self._b.expr_binary(BIN_AND, left, right)

    def visit_constraint_unique(self, c):
        # Expand to pairwise != (functionally identical to native all_different;
        # composes cleanly as a returned boolean root). Array operands -> P2.
        elems = []
        for i in c.unique_l:
            if isinstance(i, ExprFieldRefModel) and isinstance(i.fm, FieldArrayModel):
                raise BackendIncomplete("dv-solve: unique over array not yet supported")
            elems.append(i)
        if len(elems) > 1:
            refs = [self.translate(e) for e in elems]
            terms = []
            for i in range(len(refs)):
                for j in range(i + 1, len(refs)):
                    terms.append(self._b.expr_binary(BIN_NEQ, refs[i], refs[j]))
            self._result = self._conj(terms)
        else:
            self._result = self._b.expr_const(1)

    def visit_constraint_solve_order(self, c):
        # Ordering metadata only; contributes nothing to satisfiability.
        self._result = self._b.expr_const(1)

    # ------------------------------------------------------------------ #
    # Bit-select expression (native via flattening)                        #
    # ------------------------------------------------------------------ #
    #
    # NB: array sum/product are deliberately routed to fallback (below). Their
    # lowered expression depends on the array's size, which for random-sized
    # arrays is itself a solver variable; translating the (size-at-build-time)
    # sum mis-encodes that coupling. Boolector's array path handles it, so we
    # defer array aggregates to the fallback for correctness.

    def visit_expr_partselect(self, e):
        # a[hi:lo] -> extract(a, hi, lo). A single-bit select (no lower) extracts
        # bit `upper`. The extract operand must be a plain var; the extract
        # itself is lifted to an aux only when its consumer needs a var (e.g. as
        # an operand of arithmetic / a relational). `var == a[hi:lo]` compiles
        # directly without an aux.
        operand = self.translate(e.lhs, want_var=True)
        hi = int(e.upper.val())
        lo = int(e.lower.val()) if e.lower is not None else hi
        ref = self._b.expr_extract(operand, hi, lo)
        w = hi - lo + 1
        if self._want_var and self._AUX_MIN_W <= w <= self._AUX_MAX_W:
            self._result = self._materialize(ref, w, False)
            self._last_simple = True
        else:
            self._result = ref
            self._last_simple = False

    # ------------------------------------------------------------------ #
    # Explicitly-unsupported nodes (request fallback). Listed individually   #
    # so traversing base-class visits never silently clobber the result.    #
    # ------------------------------------------------------------------ #

    def _unsupported(self, node):
        raise BackendIncomplete(
            "dv-solve translator does not yet handle %s" % type(node).__name__)

    # Composite / structural
    visit_composite_field = _unsupported
    visit_generator = _unsupported
    visit_field_scalar_array = _unsupported
    # Dist (native support arrives in Phase 2)
    visit_constraint_dist = _unsupported
    visit_constraint_dist_scope = _unsupported
    visit_dist_weight = _unsupported
    # Arrays / foreach (pre-expanded; residuals -> Phase 2)
    visit_constraint_foreach = _unsupported
    visit_constraint_unique_vec = _unsupported
    visit_constraint_inline_scope = _unsupported
    visit_constraint_override = _unsupported
    visit_constraint_dynref = _unsupported
    # Expression forms still routed to fallback
    visit_expr_array_sum = _unsupported
    visit_expr_array_product = _unsupported
    visit_expr_dynamic = _unsupported
    visit_expr_indexed_dynref = _unsupported
    visit_expr_indexed_fieldref = _unsupported
    visit_expr_array_subscript = _unsupported
    visit_expr_range = _unsupported
    visit_expr_rangelist = _unsupported
