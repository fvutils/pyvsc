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
        # Count of auxiliary vars allocated so far (via _new_aux). Used to detect
        # when translating an implication/if guard had to lift arithmetic into an
        # aux — an unsound shape for the *primary* engine's disjunction encoding
        # (see _translate_guarded_cond).
        self._aux_count = 0
        # Set True when a constraint was emitted that the primary bounds engine
        # cannot solve soundly (an aux-lifted logical-combination guard — F-E3),
        # so the backend must route this RandSet straight to the BV-SAT engine
        # (force-serve), exactly like a >64-bit field. The encoding emitted *is*
        # correct; only the primary's propagation over it is unsound, and BV-SAT
        # is complete, so serving via BV-SAT is sound (Phase F / F-2 burn-down).
        self.requires_bvsat = False
        # Fields carrying a native ``dist``: their membership is owned by the dist
        # encoding (add_dist + the dist's domain-twin), so the native
        # EXPR_IN_RANGES membership shortcut (try_native_in_ranges) must NOT also
        # fire for them — emitting a second hard membership propagator over a dist
        # var breaks the dist compile. The backend populates this before
        # translating constraints.
        self.dist_fields = set()
        # Soft-translation context, mirroring ``ConstraintModel.build(btor, soft)``.
        # A ``soft(expr)`` only *exists* as a constraint when built in the soft
        # context (``ConstraintSoftModel.build`` returns ``None`` for ``soft=False``).
        # So when translating the **hard** constraint tree (default), a soft node
        # must translate to *nothing* (the conjunction identity, ``true``) — it is
        # enforced exclusively via the native soft list (``add_soft_constraint``).
        # When the backend's soft loop translates a soft *root*, it sets this True
        # via ``translate_soft`` so the soft's expr is materialized for
        # ``add_soft_constraint``. Translating a soft as hard would silently turn a
        # preference into a requirement (a soundness bug) — see SC-1.
        self._soft_ctx = False
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
        # ``_soft_ctx`` MUST be part of the memo key: a soft model shared between
        # the hard tree (a guarded soft's enclosing ``if_else``/scope, where a soft
        # drops to ``true``) and the soft list (the priority-bearing
        # ``ConstraintImpliesModel`` whose body must materialize the soft's expr)
        # translates to *different* refs by context. Without it, whichever context
        # runs first (hard, always — see ``_populate_builder``) caches its result
        # and the guarded soft body is silently lost (``(!cond) || true``),
        # dropping the preference entirely.
        key = (id(node), ctx_width, want_var, self._soft_ctx)
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
                "dv-solve translator does not handle node %s" % type(node).__name__,
                reason_code="translator-unsupported")
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
        aux_ref = self._new_aux(w, is_signed)
        self._b.add_constraint(self._b.expr_binary(BIN_EQ, aux_ref, ref))
        return aux_ref

    def _new_aux(self, width, is_signed) -> int:
        """Declare a fresh auxiliary variable of the given width/sign over its
        natural width range and return its var ref (no defining constraint —
        the caller adds one, e.g. ``aux == <op>`` or a native ``expr_sum``)."""
        w = int(width)
        signed = bool(is_signed)
        if signed:
            lo = -(1 << (w - 1))
            hi = (1 << (w - 1)) - 1
        else:
            lo = 0
            hi = (1 << w) - 1
        aux = self._m.alloc_aux()
        self._aux_count += 1
        self._b.add_var(aux, w, signed, lo, hi)
        return self._b.expr_var(aux)

    def _translate_guarded_cond(self, cond_e) -> int:
        """Translate an implication / if-else *guard* (antecedent), deferring if
        it lowers unsoundly.

        An implication ``cond -> body`` is encoded as the disjunction
        ``(!cond) || body``. When ``cond`` is a **logical AND/OR of comparisons
        whose operands had to be lifted into aux variables** (arithmetic in the
        guard, e.g. ``((b-1) >= 4) & ((b-1) < 8)`` — the clog2 idiom), the
        bounds-propagation engine's propagation through ``NOT(AND(...))`` over
        aux-defined comparison operands is **unsound**: it can leave ``body``
        unconstrained even when the guard is in fact true, producing a model that
        violates the implication (confirmed by the XCHECK differential check —
        Phase E / F-E3). The failure is asymmetric and fragile (a lifted operand
        on the AND's left side triggers it; the right side may not).

        The encoding itself is correct — only the *primary* engine's reasoning
        over it is unsound — and the BV-SAT engine is complete, so rather than
        deferring the whole RandSet to the external fallback we emit the encoding
        and flag ``requires_bvsat`` so the backend force-serves it via BV-SAT
        (the same route a >64-bit field takes). A *single* relational comparison
        with arithmetic (``implies((b-1) >= 4)``) is sound on the primary and
        stays on the fast path (no flag). (Phase F / F-2: native implies-aux
        serving — previously a `bvsat`-deferred `implies-aux` residual.)"""
        aux_before = self._aux_count
        ref = self.translate(cond_e)
        lifted = self._aux_count > aux_before
        is_logical_combo = getattr(cond_e, "op", None) in (
            BinExprType.And, BinExprType.Or)
        if lifted and is_logical_combo:
            self.requires_bvsat = True
        return self._to_bool(ref, cond_e)

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
            # Size the literal by the *value's* magnitude, not the declared
            # width: a pyvsc Python-int literal defaults to width 32 regardless
            # of magnitude (a 128-bit constant reports width() == 32), so trusting
            # e.width() would route a >64-bit value through the 64-bit path below
            # and truncate it (expr_const wraps to int64). The value bit-length is
            # authoritative.
            if signed:
                vw = (v if v >= 0 else ~v).bit_length() + 1
            else:
                vw = v.bit_length()
            w = max(int(e.width()) if e.width() else 0, vw, 1)
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

    @staticmethod
    def _value_fits_width(v, w, signed):
        """True iff integer ``v`` is representable in a ``w``-bit field of the
        given signedness — i.e. a variable of that width could actually hold it."""
        if signed:
            return -(1 << (w - 1)) <= v <= (1 << (w - 1)) - 1
        return 0 <= v <= (1 << w) - 1

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
                raise BackendIncomplete("dv-solve: unsupported binary op %s" % str(e.op),
                                        reason_code="translator-unsupported")

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
            # The compiler handles `var/const == <op>` (one plain side). When the
            # operands are the SAME width, keep both raw and only lift one if
            # *neither* is plain. When the widths DIFFER, the native equality
            # reconciles at the *min* width — it truncates the wider operand — so a
            # wider, non-constant operand that can exceed the narrow one's range is
            # silently wrapped (e.g. an `arr.sum` aux of value 306 compared to an
            # 8-bit comparand passes as 306 ≡ 50 mod 256). Boolector zero/sign-
            # extends the narrow side and compares at the *max* width. So when the
            # widths differ and neither side is a pure constant, materialize both
            # to plain operands and extend the narrower to ctx_width before
            # comparing. A constant operand never wraps (it is a fixed value), so
            # `var == const` keeps the direct, un-extended form.
            from vsc.visitors.is_const_expr_visitor import IsConstExprVisitor
            _isc = IsConstExprVisitor()
            lhs_const = _isc.is_const(e.lhs)
            rhs_const = _isc.is_const(e.rhs)
            # A constant whose magnitude exceeds the width of a *field reference*
            # it is compared to can never equal it — a width-w field is bounded by
            # its width — so the equality is statically false (Ne: true). Without
            # this the native min-width equality truncates the constant to the
            # field width (`a(8) == 500` -> `a == 244`) and reports a wrong SAT;
            # matching Boolector here is what lets the empty-domain RandSet routed
            # to BV-SAT (the backend's near-unsat path) prove UNSAT as Boolector
            # does. Restricted to a bare field ref: a value-op (e.g. `a*b`) can
            # exceed its operands' width (the literal up-sizes the expression —
            # `a*b == 256` is SAT for uint8 a,b), so its declared width does NOT
            # bound its value and the short-circuit would wrongly reject it.
            if lhs_const != rhs_const:
                if lhs_const:                      # the variable side is e.rhs
                    vexpr, vw, vsigned, cexpr = e.rhs, rhs_w, e.rhs.is_signed(), e.lhs
                else:                               # the variable side is e.lhs
                    vexpr, vw, vsigned, cexpr = e.lhs, lhs_w, e.lhs.is_signed(), e.rhs
                if isinstance(vexpr, ExprFieldRefModel):
                    try:
                        cv = int(cexpr.val())
                    except Exception:
                        cv = None
                    if cv is not None and not self._value_fits_width(cv, vw, vsigned):
                        self._result = self._b.expr_const(
                            0 if e.op == BinExprType.Eq else 1)
                        self._last_simple = False
                        return
            extend = (lhs_w != rhs_w and not lhs_const and not rhs_const)
            lhs = self.translate(e.lhs, ctx_width, want_var=extend)
            lhs_simple = self._last_simple
            rhs = self.translate(e.rhs, ctx_width, want_var=extend)
            rhs_simple = self._last_simple
            if extend:
                if lhs_w < ctx_width:
                    lhs = self._b.expr_extend(
                        lhs, lhs_w, ctx_width, e.lhs.is_signed())
                if rhs_w < ctx_width:
                    rhs = self._b.expr_extend(
                        rhs, rhs_w, ctx_width, e.rhs.is_signed())
            elif not lhs_simple and not rhs_simple:
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
            raise BackendIncomplete("dv-solve: unsupported unary op %s" % str(e.op),
                                    reason_code="translator-unsupported")
        # De Morgan rewrite for negated membership `!(x in S)` (`not_inside`).
        # By De Morgan it is a *conjunction* of per-entry negations — `x != v` for
        # each scalar, `(x < lo) || (x > hi)` for each range. The bounds engine
        # decides that conjunctive form natively (each `x != v` simply punches a
        # hole in x's domain), whereas the literal `NOT(OR(x == v ...))` this would
        # otherwise lower to stalls its disjunction propagation and defers to
        # BV-SAT (`bvsat-sat-deferred`). The rewrite is semantics-preserving
        # (verified against Boolector by XCHECK) and lives here, in the dv-solve
        # translator, on purpose: it re-expresses the constraint using primitives
        # the dv-solve engine already has, and leaves Boolector's own encoding
        # (the XCHECK reference) untouched.
        from vsc.model.expr_in_model import ExprInModel
        if isinstance(e.expr, ExprInModel):
            dm = self._negated_membership(e.expr)
            if dm is not None:
                self._result = self.translate(dm)
                self._last_simple = False
                return
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
                # 'in' over an array's elements: lhs ∈ {arr[0], …, arr[n-1]} ==
                # OR_i (lhs == arr[i]) over the active elements — the unambiguous
                # set-membership semantics (matches Boolector's expansion). n is
                # the fixed size or a resolved randsz size; a co-solved randsz
                # size defers (reason_code="array") via _array_elem_count, exactly
                # as the aggregate path does. An empty active set also defers —
                # its membership is the constant False, which the OR-fold below
                # can't represent as a model node without spuriously reading as
                # always-true when it is the sole rangelist entry.
                from vsc.model.expr_fieldref_model import ExprFieldRefModel as _FR
                arr = r.fm
                n = self._array_elem_count(arr)
                if n < 1:
                    # An empty array is the empty set for this entry, i.e. the
                    # constant False as a membership-OR leaf — skip it; it changes
                    # nothing, so `a in {<empty list>, 10, 12, 14}` reduces to
                    # `a in {10, 12, 14}`. If it is the *sole* entry the whole `in`
                    # is empty-set membership, handled after the loop.
                    continue
                term = None
                for i in range(n):
                    eq = ExprBinModel(e.lhs, BinExprType.Eq, _FR(arr.field_l[i]))
                    term = eq if term is None \
                        else ExprBinModel(term, BinExprType.Or, eq)
            else:
                term = ExprBinModel(e.lhs, BinExprType.Eq, r)
            expr = term if expr is None else ExprBinModel(expr, BinExprType.Or, term)
        if expr is None:
            if e.rhs.rl:
                # Every rangelist entry reduced away (all empty arrays): this is
                # membership over the empty set. Defer for the degenerate semantics
                # rather than fabricate a constant (the prior conservative path).
                raise BackendIncomplete(
                    "dv-solve: 'in' over empty set", reason_code="array")
            self._result = self._b.expr_const(1)
        else:
            self._result = self.translate(expr)

    def _negated_membership(self, e_in):
        """Build the De Morgan ExprModel tree for ``!(lhs in S)`` — a conjunction
        of per-entry negations — or ``None`` if it cannot be lowered this way:

          * empty set (``!(x in {})``): leave to the generic NOT path so the
            existing (degenerate) semantics are preserved, and
          * membership over an array's elements: leave to ``visit_expr_in`` so it
            raises the documented ``array`` deferral.
        """
        from vsc.model.expr_bin_model import ExprBinModel
        expr = None
        for r in e_in.rhs.rl:
            if isinstance(r, ExprRangeModel):
                # !(lo <= x <= hi) == (x < lo) || (x > hi)
                term = ExprBinModel(
                    ExprBinModel(e_in.lhs, BinExprType.Lt, r.lhs),
                    BinExprType.Or,
                    ExprBinModel(e_in.lhs, BinExprType.Gt, r.rhs))
            elif isinstance(r, ExprFieldRefModel) and isinstance(r.fm, FieldArrayModel):
                return None
            else:
                term = ExprBinModel(e_in.lhs, BinExprType.Ne, r)
            expr = term if expr is None else ExprBinModel(expr, BinExprType.And, term)
        return expr

    # ------------------------------------------------------------------ #
    # Constraint nodes (translate to boolean roots)                        #
    # ------------------------------------------------------------------ #

    def visit_constraint_expr(self, c):
        # `const_table[rand_idx] <cmp> const` is a pure index *selector*, not a
        # symbolic select: rewrite it to a membership constraint on the index.
        sel = self.try_const_table_select(c.e)
        if sel is not None:
            self._result = sel
            return
        # A top-level `field inside {ranges}` over constant ranges compiles to a
        # native EXPR_IN_RANGES membership propagator (sound, and unlike the
        # OR-of-ranges encoding it does not defeat the compiler's _flatten_or).
        native = self.try_native_in_ranges(c.e)
        if native is not None:
            self._result = native
            return
        self._result = self._to_bool(self.translate(c.e), c.e)

    # Comparison ops eligible for the const-table selector rewrite, with their
    # Python evaluators (applied to concrete table values at compile time).
    _TABLE_CMP_FN = {
        BinExprType.Eq: lambda a, b: a == b,
        BinExprType.Ne: lambda a, b: a != b,
        BinExprType.Lt: lambda a, b: a < b,
        BinExprType.Le: lambda a, b: a <= b,
        BinExprType.Gt: lambda a, b: a > b,
        BinExprType.Ge: lambda a, b: a >= b,
    }

    def try_const_table_select(self, e):
        """Rewrite ``table[idx] <cmp> const`` (table a non-rand fixed array, idx a
        rand var) into ``idx inside {i : table[i] <cmp> const}`` — a single
        small-domain membership on the index.

        When the array is not randomized it is a fixed lookup table, so the
        selected element is a *constant function of the index*: the feasible index
        set is computable here in O(n), yielding one native ``EXPR_IN_SET`` on idx
        instead of an n-arm ITE select. That is both far cheaper (no n baked-const
        arms, no per-element propagators) and strictly more solvable — the ITE
        encoding can't reverse-propagate ``arm == K`` back to the index, so a
        plain ``table[idx] == K`` otherwise deferred. Returns the constraint ref,
        or ``None`` to fall through to the general path."""
        from vsc.model.expr_bin_model import ExprBinModel
        from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel
        from vsc.visitors.is_const_expr_visitor import IsConstExprVisitor
        if not isinstance(e, ExprBinModel):
            return None
        fn = self._TABLE_CMP_FN.get(e.op)
        if fn is None:
            return None
        is_const = IsConstExprVisitor().is_const
        # One side is the table subscript, the other a compile-time constant.
        if isinstance(e.lhs, ExprArraySubscriptModel) and is_const(e.rhs):
            sub, k_expr, table_on_left = e.lhs, e.rhs, True
        elif isinstance(e.rhs, ExprArraySubscriptModel) and is_const(e.lhs):
            sub, k_expr, table_on_left = e.rhs, e.lhs, False
        else:
            return None
        if not isinstance(sub.lhs, ExprFieldRefModel) \
                or not isinstance(sub.lhs.fm, FieldArrayModel):
            return None
        arr = sub.lhs.fm
        # Only a *non-rand* table (every element constant at solve time) with a
        # *rand, non-constant* index is a selector; anything else is a genuine
        # symbolic select and stays on the general path.
        if any(getattr(f, "is_used_rand", False) for f in arr.field_l):
            return None
        if is_const(sub.rhs):
            return None
        try:
            n = self._array_elem_count(arr)
        except Exception:
            return None
        if n < 1:
            return None
        # The index must lower to a plain solver var (EXPR_IN_SET's value).
        try:
            idx_w = int(sub.rhs.width())
        except Exception:
            return None
        if not (self._AUX_MIN_W <= idx_w <= self._AUX_MAX_W):
            return None
        try:
            # k_expr is an expression (``.val()`` method); the table elements are
            # field models whose current value is the ``.val`` attribute — exactly
            # the constant ``_ref_for_field`` would bake for a non-rand field.
            k = int(k_expr.val())
            elems = [int(arr.field_l[i].val) for i in range(n)]
        except Exception:
            return None
        # feasible = { i : table[i] <cmp> K } (respecting operand order).
        feasible = [i for i in range(n)
                    if (fn(elems[i], k) if table_on_left else fn(k, elems[i]))]
        idx_ref = self.translate(sub.rhs, want_var=True)
        if not self._last_simple:
            idx_ref = self._materialize(idx_ref, idx_w, bool(sub.rhs.is_signed()))
        if not feasible:
            # No index satisfies the constraint -> UNSAT. `idx < idx` is a
            # guaranteed-false root the compiler rejects cleanly.
            self._last_simple = False
            return self._b.expr_binary(BIN_LT, idx_ref, idx_ref)
        self._last_simple = False
        return self._b.expr_in_set(
            idx_ref, [self._b.expr_const(i) for i in feasible])

    def try_native_in_ranges(self, e):
        """If ``e`` is a constraint-root ``field inside {...}`` whose lhs is a
        scalar field var and whose rangelist is >=2 constant entries with at
        least one real range, emit a native EXPR_IN_RANGES node and return its
        ref. Otherwise return ``None`` (caller falls back to the OR encoding).

        Restricted to the multi-range case because: a single range / all-scalar
        set already compiles soundly on the primary (bound tightening / a
        disjunctive clause of equalities); only a disjunction containing a range
        leaf defeats ``_flatten_or`` and was deferring (Phase G G-2). Membership
        is constraint-root only (the node is not a boolean sub-expression), so
        this is called from ``visit_constraint_expr`` and the gapped-domain
        re-assertion, never mid-expression."""
        from vsc.model.expr_in_model import ExprInModel
        from vsc.model.expr_range_model import ExprRangeModel
        from vsc.model.expr_literal_model import ExprLiteralModel
        if not isinstance(e, ExprInModel):
            return None
        if not isinstance(e.lhs, ExprFieldRefModel):
            return None
        if isinstance(e.lhs.fm, FieldArrayModel):
            return None  # membership of an array field, not a scalar var
        if e.lhs.fm in self.dist_fields:
            return None  # dist owns this field's membership encoding
        pairs = []
        has_range = False
        for r in e.rhs.rl:
            if isinstance(r, ExprRangeModel):
                if not (isinstance(r.lhs, ExprLiteralModel)
                        and isinstance(r.rhs, ExprLiteralModel)):
                    return None  # variable range bound -> keep the OR path
                pairs.append((self.translate(r.lhs), self.translate(r.rhs)))
                has_range = True
            elif isinstance(r, ExprLiteralModel):
                s = self.translate(r)
                pairs.append((s, s))
            else:
                return None  # array-element or non-const entry
        if len(pairs) < 2 or not has_range:
            return None
        ref = self._b.expr_in_ranges(self.translate(e.lhs), pairs)
        self._last_simple = False
        return ref

    def translate_soft(self, c) -> int:
        """Translate a soft *root* (the backend's soft loop) — materialize the
        soft's expr (and any nested soft inside a guarded ``ConstraintImpliesModel``
        soft) so it can be handed to native ``add_soft_constraint``. Restores the
        prior context so a soft loop cannot leak the soft context into later hard
        translation."""
        saved = self._soft_ctx
        self._soft_ctx = True
        try:
            return self.translate(c)
        finally:
            self._soft_ctx = saved

    def visit_constraint_soft(self, c):
        # In the hard tree a soft contributes nothing (it is enforced via the
        # native soft list) — mirror ``ConstraintSoftModel.build(soft=False)`` ->
        # ``None``. Only a soft *root* (``translate_soft``) materializes its expr.
        if self._soft_ctx:
            self._result = self._to_bool(self.translate(c.expr), c.expr)
        else:
            self._result = self._b.expr_const(1)
            self._last_simple = False

    def visit_constraint_scope(self, c):
        self._result = self._conj([self.translate(cc) for cc in c.constraint_l])

    def visit_constraint_block(self, c):
        self.visit_constraint_scope(c)

    def visit_expr_indexed_dynref(self, e):
        # A reference to a named ``@vsc.dynamic_constraint`` block, enabled inside
        # ``randomize_with`` (e.g. ``it.a_small()`` or ``it.a_small() | it.a_large()``).
        # Mirror ``ExprIndexedDynRefModel.build``: resolve the owning field, index
        # the dynamic-constraint block, and conjoin its constraints into a single
        # width-1 boolean root. ``width() == 1`` so the enclosing ``visit_constraint_expr``
        # keeps it boolean, and a logical combination (``|``/``&`` of two refs) is
        # handled by ``visit_expr_bin`` on the width-1 results.
        from vsc.visitors.expr2field_visitor import Expr2FieldVisitor
        fm = Expr2FieldVisitor().field(e.root, True)
        block = fm.constraint_dynamic_model_l[e.idx]
        self._result = self._conj([self.translate(cc) for cc in block.constraint_l])
        self._last_simple = False

    def visit_constraint_dynref(self, e):
        # ``ExprDynRefModel`` — the non-indexed sibling of ``ExprIndexedDynRefModel``;
        # ``dynamic_constraint_t.__call__`` yields one holding the block model
        # directly. Same encoding: conjoin the block's constraints to a width-1 root.
        # (Soft members never reach here — a soft-bearing dynamic block is routed
        # through the RandSet-level soft path, not translated as a hard conjunction.)
        self._result = self._conj([self.translate(cc) for cc in e.c.constraint_l])
        self._last_simple = False

    def _const_cond(self, cond_e, allow_field_fold=False):
        """If ``cond_e`` is a pure-constant expression (no field references), return
        its truth value as 0/1; otherwise ``None``.

        ``allow_field_fold`` additionally folds a guard that references only fields
        *not* solved in this RandSet (a solve-time constant) — enabled only for a
        guard enclosing a dist, so the broader behavior change stays scoped to
        conditional dist.

        Array ``foreach`` expansion substitutes the loop index with a literal, so a
        guard such as ``i != j`` or ``i < 4`` becomes a comparison of *literals*
        (e.g. ``0 != 1``). Translating that through the generic implication path
        yields a disjunction ``(!cond) || body`` whose ``cond`` is a constant the
        native compiler does not fold — and the bounds-propagation engine cannot
        propagate through the residual OR, so the search reports incomplete and the
        whole RandSet defers (the dominant `foreach` idiom). Folding the guard here
        emits the taken branch directly, keeping the problem in the
        propagator-friendly conjunctive form. Restricted to pure constants (via
        ``IsConstExprVisitor``) so the fold is solve-invariant — no plan-cache /
        reuse staleness, and a guard that genuinely depends on a rand var keeps the
        disjunction path."""
        from vsc.visitors.is_const_expr_visitor import IsConstExprVisitor
        if IsConstExprVisitor().is_const(cond_e):
            try:
                return 1 if int(cond_e.val()) != 0 else 0
            except Exception:
                return None
        if not allow_field_fold:
            # Without an explicit opt-in, only *pure-literal* guards fold (the
            # original foreach-index behavior). The extended non-rand-field fold
            # below is enabled only by callers that need it (a guard enclosing a
            # dist — see _branch_contains_dist), so it cannot perturb unrelated
            # conditional constructs.
            return None
        # Extended fold: a guard that references only fields *not* solved in this
        # RandSet (non-rand state, or vars solved in an earlier RandSet) is a
        # solve-time constant too. Folding it is what lets a *conditional dist*
        # solve on the primary engine (and thus honor its native add_dist
        # weighting) rather than leaving a residual disjunction the bounds engine
        # can't decide — which would route to BV-SAT and drop the weighting. To
        # stay plan-cache-safe we register every referenced field as a const_field
        # (mirroring _ref_for_field), so a later randomize with a changed guard
        # value rebuilds rather than reusing a stale fold.
        fields = self._collect_guard_fields(cond_e)
        if fields is None or any(self._m.has(f) for f in fields):
            return None
        try:
            v = int(cond_e.val())
        except Exception:
            return None
        for f in fields:
            try:
                self.const_fields[f] = int(f.val)
            except Exception:
                return None
        return 1 if v != 0 else 0

    def _collect_guard_fields(self, cond_e):
        """Collect every FieldModel referenced by a guard expression, or ``None``
        if a node type we don't classify is encountered (then we conservatively
        decline to fold). Used by _const_cond's non-rand-field fold path."""
        from vsc.model.model_visitor import ModelVisitor

        class _Collect(ModelVisitor):
            def __init__(self):
                super().__init__()
                self.fields = []

            def visit_expr_fieldref(self, e):
                self.fields.append(e.fm)

        c = _Collect()
        try:
            cond_e.accept(c)
        except Exception:
            return None
        return c.fields

    def _branch_contains_dist(self, nodes):
        """True iff any constraint in ``nodes`` (a constraint or list thereof)
        contains a dist scope — directly or wrapped in an override. Gates the
        non-rand-field guard fold (``_const_cond``) so it applies only where it is
        needed (conditional dist) and cannot perturb unrelated guarded blocks."""
        from vsc.model.constraint_dist_scope_model import ConstraintDistScopeModel
        from vsc.model.constraint_override_model import ConstraintOverrideModel

        if not isinstance(nodes, (list, tuple)):
            nodes = [nodes]
        stack = list(nodes)
        while stack:
            n = stack.pop()
            if isinstance(n, ConstraintDistScopeModel):
                return True
            if isinstance(n, ConstraintOverrideModel):
                stack.append(n.new_constraint)
                continue
            sub = getattr(n, "constraint_l", None)
            if sub:
                stack.extend(sub)
        return False

    @staticmethod
    def _branch_is_conjunctive(branch) -> bool:
        """True if an if/else branch is a scope holding more than one statement,
        i.e. it lowers to an ``AND`` (the unsound Boolean-guard primary case)."""
        if branch is None:
            return False
        return len(getattr(branch, "constraint_l", ())) > 1

    def visit_constraint_implies(self, c):
        folded = self._const_cond(
            c.cond, allow_field_fold=self._branch_contains_dist(c.constraint_l))
        if folded == 0:
            # Guard is constant-false: the implication is vacuously satisfied.
            self._result = self._b.expr_const(1)
            return
        if folded == 1:
            # Guard is constant-true: assert the body unconditionally.
            self._result = self._conj([self.translate(cc) for cc in c.constraint_l])
            return
        cond = self._translate_guarded_cond(c.cond)
        # A *conjunctive* body (more than one statement) makes the implication
        # `(!cond) || (b0 && b1 && ...)` carry an AND leaf in its top-level OR.
        # The native compiler's `_flatten_or` can only handle single-comparison
        # OR leaves, so it falls back to a Boolean-guard encoding whose primary
        # propagation is **unsound** — it can leave the body unconstrained even
        # when the guard is true, producing a model that violates the implication
        # (same failure family as the lifted-logical-combo guard above; confirmed
        # by XCHECK on `implies(c==0): a==0; b==0`). The encoding is correct and
        # BV-SAT is complete, so force-serve it via BV-SAT. A single-comparison
        # body (`implies(g): a==0`) lowers to a 2-clause disjunction the primary
        # handles soundly and stays on the fast path. (Phase G — pre-existing
        # primary reification gap, exposed once unsigned-64 stopped deferring.)
        if len(c.constraint_l) > 1:
            self.requires_bvsat = True
        body = self._conj([self.translate(cc) for cc in c.constraint_l])
        # cond -> body  ==  (!cond) || body  (logical OR; the native compiler
        # does not accept a top-level ite as a constraint).
        self._result = self._b.expr_binary(
            BIN_OR, self._b.expr_unary(UN_NOT, cond), body)

    def visit_constraint_if_else(self, c):
        branches = [c.true_c] + ([c.false_c] if c.false_c is not None else [])
        folded = self._const_cond(
            c.cond, allow_field_fold=self._branch_contains_dist(branches))
        if folded == 1:
            # Constant-true guard: only the then-branch applies.
            self._result = self.translate(c.true_c)
            return
        if folded == 0:
            # Constant-false guard: only the else-branch (if any) applies.
            self._result = (self.translate(c.false_c)
                            if c.false_c is not None else self._b.expr_const(1))
            return
        # A conjunctive branch (a scope with >1 statement) makes the encoded
        # `(!cond) || branch` carry an AND leaf, which the primary handles via
        # the unsound Boolean-guard fallback (see visit_constraint_implies). Force
        # such if/else through the complete BV-SAT engine.
        if self._branch_is_conjunctive(c.true_c) or \
                self._branch_is_conjunctive(c.false_c):
            self.requires_bvsat = True
        cond = self._translate_guarded_cond(c.cond)
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

    # Pairwise-!= expansion of `unique` is O(n^2); above this many operands the
    # term count is impractical for the bounds engine — defer (Phase C §5).
    _MAX_UNIQUE_ELEMS = 64

    def visit_constraint_unique(self, c):
        # Expand to pairwise != (functionally identical to native all_different;
        # composes cleanly as a returned boolean root). A fixed-size array operand
        # is expanded into its element fields (Phase C-4, mirroring Boolector's
        # ConstraintUniqueModel._add_list_elems); a random-sized array is served by
        # the size-guarded encoding in `_unique_randsz` (Phase F arrays burn-down).
        from vsc.model.expr_fieldref_model import ExprFieldRefModel as _FR
        # A lone `unique(arr)` over a random-sized array is served size-guarded.
        # Mixing a randsz array with other operands is not a corpus shape — defer.
        if len(c.unique_l) == 1:
            only = c.unique_l[0]
            if isinstance(only, ExprFieldRefModel) \
                    and isinstance(only.fm, FieldArrayModel) \
                    and getattr(only.fm, "is_rand_sz", False):
                self._result = self._unique_randsz(only.fm)
                return
        elems = []
        for i in c.unique_l:
            if isinstance(i, ExprFieldRefModel) and isinstance(i.fm, FieldArrayModel):
                arr = i.fm
                if getattr(arr, "is_rand_sz", False):
                    raise BackendIncomplete(
                        "dv-solve: unique mixing a random-sized array with other "
                        "operands (size-guarded mix not supported)",
                        reason_code="array")
                for f in arr.field_l:
                    elems.append(_FR(f))
            else:
                elems.append(i)
        if len(elems) > self._MAX_UNIQUE_ELEMS:
            raise BackendIncomplete(
                "dv-solve: unique over %d elements exceeds the pairwise cap"
                % len(elems), reason_code="array")
        if len(elems) > 1:
            refs = [self.translate(e) for e in elems]
            terms = []
            for i in range(len(refs)):
                for j in range(i + 1, len(refs)):
                    terms.append(self._b.expr_binary(BIN_NEQ, refs[i], refs[j]))
            self._result = self._conj(terms)
        else:
            self._result = self._b.expr_const(1)

    def _unique_randsz(self, arr):
        """Size-guarded `unique` over a random-sized array — the active set is
        ``field_l[0:size]`` and only active elements must be distinct.

        Two cases (mirroring `_array_elem_count`):
          * `size` resolved earlier (not co-solved in this RandSet) — the active
            prefix is fixed, so we pairwise-`!=` the resolved prefix directly
            (sound because we only read `size.get_val()` when `size` is NOT in the
            idmap, so its value is committed by a prior RandSet, never stale).
          * `size` co-solved in this RandSet — its value is solver-chosen, so each
            pair is guarded: ``(j < size) -> elem[i] != elem[j]`` for i<j, encoded
            as ``(j >= size) || (elem[i] != elem[j])`` (j is the larger index, and
            j<size implies i<size, so guarding the larger index alone is exact)."""
        from vsc.model.expr_fieldref_model import ExprFieldRefModel as _FR
        from vsc.model.expr_bin_model import ExprBinModel
        from vsc.model.expr_literal_model import ExprLiteralModel
        if not self._m.has(arr.size):
            # Resolved size: fixed active prefix.
            n = int(arr.size.get_val())
            if n > self._MAX_UNIQUE_ELEMS:
                raise BackendIncomplete(
                    "dv-solve: unique over %d elements exceeds the pairwise cap"
                    % n, reason_code="array")
            refs = [self.translate(_FR(arr.field_l[k])) for k in range(n)]
            terms = [self._b.expr_binary(BIN_NEQ, refs[i], refs[j])
                     for i in range(len(refs)) for j in range(i + 1, len(refs))]
            return self._conj(terms)
        # Co-solved size: guard each max-size pair on the active prefix.
        M = len(arr.field_l)
        if M > self._MAX_UNIQUE_ELEMS:
            raise BackendIncomplete(
                "dv-solve: unique over %d elements exceeds the pairwise cap"
                % M, reason_code="array")
        sw = int(arr.size.width())
        terms = []
        for i in range(M):
            for j in range(i + 1, M):
                guard = ExprBinModel(ExprLiteralModel(j, False, sw),
                                     BinExprType.Ge, _FR(arr.size))
                neq = ExprBinModel(_FR(arr.field_l[i]), BinExprType.Ne,
                                   _FR(arr.field_l[j]))
                terms.append(self.translate(
                    ExprBinModel(guard, BinExprType.Or, neq)))
        return self._conj(terms)

    def visit_constraint_solve_order(self, c):
        # Ordering metadata only; contributes nothing to satisfiability.
        self._result = self._b.expr_const(1)

    def visit_constraint_override(self, c):
        # An override replaces orig_constraint with new_constraint (Boolector
        # builds new_constraint). We translate the replacement: a dist expansion
        # (ConstraintDistScopeModel carrying the hard `inside` membership; the
        # weighting is applied separately via add_dist on dist_field_m), or
        # ArrayConstraintBuilder's foreach/array expansion (a ConstraintInlineScope
        # of per-element constraints). The inline-scope translation conjoins the
        # *hard* per-element constraints and drops the *soft* ones (SC-1) — the
        # softs are enforced via the native soft list, exactly as Boolector's
        # `build(soft=False)` drops them (ConstraintSoftModel.build -> None). This
        # is sound *because* a soft node now translates to nothing in the hard
        # context (visit_constraint_soft); conjoining a soft as hard would turn a
        # preference into a requirement.
        self._result = self.translate(c.new_constraint)
        self._last_simple = False

    def visit_constraint_dist_scope(self, c):
        # Conjoin the dist scope's constraints. On the native path that scope
        # holds only its hard `inside` membership (zero-weight exclusion
        # implications and the swizzler soft are emitted only on the fallback
        # path), so the conjunction is exactly that membership.
        self._result = self._conj([self.translate(cc) for cc in c.constraint_l])
        self._last_simple = False

    # ------------------------------------------------------------------ #
    # Array aggregates (Phase C-2: fixed-size native)                      #
    # ------------------------------------------------------------------ #
    #
    # NB: a random-sized array couples the aggregate's active element set to a
    # solver variable (`arr.size`), so translating the size-at-build-time chain
    # would mis-encode it (a silent wrong answer). Fixed-size aggregates are
    # encoded natively here; random-sized arrays defer to the fallback until the
    # size-guarded encoding lands (Phase C-3).

    # The native n-ary sum propagator (EXPR_SUM) caps the summand count.
    _MAX_SUM_VARS = 64

    def _array_elem_count(self, arr):
        """The active element count of ``arr`` for an aggregate.

        Fixed-size: the declared size. Random-sized (Phase C-3): pyvsc partitions
        the array's ``size`` into its own RandSet, solved (by dependency order)
        *before* the element RandSet that carries the aggregate — so by the time we
        translate the aggregate, ``size`` is already resolved to a constant and the
        active prefix ``field_l[0:size]`` is fixed. We sum over that prefix, exactly
        as Boolector's ``get_sum_expr`` does (it reads ``size.get_val()``). The
        guard: if ``size`` is instead *co-solved* in this same RandSet (in the
        idmap), its value is not yet known here, so the aggregate would need a
        size-guarded ``ite``-prefix — defer rather than read a stale size."""
        if getattr(arr, "is_rand_sz", False) and self._m.has(arr.size):
            raise BackendIncomplete(
                "dv-solve: aggregate over a co-solved random-sized array "
                "(size-guarded prefix not yet supported)", reason_code="array")
        return int(arr.size.get_val())

    def visit_expr_array_sum(self, e):
        # arr.sum -> a result aux constrained `result == Σ elem[i]` via the native
        # n-ary sum propagator. The result is returned as a plain var so the
        # enclosing constraint (`arr.sum == X`, `arr.sum < K`) compiles directly.
        from vsc.model.expr_fieldref_model import ExprFieldRefModel
        arr = e.arr
        n = self._array_elem_count(arr)
        if n == 0:
            self._result = self._b.expr_const(0)
            self._last_simple = True
            return
        if n > self._MAX_SUM_VARS:
            raise BackendIncomplete(
                "dv-solve: array sum over %d elements exceeds the native "
                "%d-summand cap" % (n, self._MAX_SUM_VARS), reason_code="array")
        # Width matches pyvsc's get_sum_width() (elem_w + clog2(size)) so the sum
        # can't overflow and width reconciliation with the comparison RHS matches.
        rw = int(e.width())
        if rw > self._AUX_MAX_W:
            raise BackendIncomplete(
                "dv-solve: array sum result width %d exceeds aux range" % rw,
                reason_code="array")
        elem_refs = [self.translate(ExprFieldRefModel(arr.field_l[i]),
                                    ctx_width=rw, want_var=True)
                     for i in range(n)]
        result_ref = self._new_aux(rw, e.is_signed())
        self._b.add_constraint(self._b.expr_sum(result_ref, elem_refs))
        self._result = result_ref
        self._last_simple = True

    def visit_expr_array_product(self, e):
        # arr.product -> a left-folded BIN_MUL chain (decision §6.4; no native
        # n-ary product). Each partial product is materialized into a plain var so
        # the modular mul propagator handles it and the enclosing constraint sees a
        # variable. The fold width follows pyvsc's model (ExprArrayProductModel is
        # 64-bit); partials are sized to the aux range and wrap-match Boolector
        # below 2^aux_w (documented caveat for very large products).
        from vsc.model.expr_fieldref_model import ExprFieldRefModel
        arr = e.arr
        n = self._array_elem_count(arr)
        signed = e.is_signed()
        if n == 0:
            self._result = self._b.expr_const(0)
            self._last_simple = True
            return
        # Cap the fold width at the aux range; pyvsc's product is nominally 64-bit
        # but the modular propagators top out at _AUX_MAX_W. This matches Boolector
        # for any product that fits — the realistic case for a `product ==`/`<`
        # constraint — and is the documented §5 caveat otherwise.
        fw = min(int(e.width()), self._AUX_MAX_W)
        acc = self.translate(ExprFieldRefModel(arr.field_l[0]),
                             ctx_width=fw, want_var=True)
        for i in range(1, n):
            elem = self.translate(ExprFieldRefModel(arr.field_l[i]),
                                  ctx_width=fw, want_var=True)
            prod = self._b.expr_binary(BIN_MUL, acc, elem)
            acc = self._materialize(prod, fw, signed)
        self._result = acc
        self._last_simple = True

    # ------------------------------------------------------------------ #
    # Array element references (Phase C-1)                                 #
    # ------------------------------------------------------------------ #
    #
    # `foreach` expansion substitutes the loop index with a literal, so most
    # subscript / indexed-field references that reach the translator resolve to a
    # *fixed* element field. We translate those directly to the element's var/const
    # ref. A genuinely variable (rand) index — no constant resolution — defers
    # (native expr_array_select would handle it but needs contiguous element ids;
    # no current corpus shape requires it, so it stays a guarded defer).

    def _const_subscript_index(self, sub):
        """Return an ExprArraySubscriptModel's constant index, or None if its index
        is not a pure constant (e.g. a rand var)."""
        from vsc.visitors.is_const_expr_visitor import IsConstExprVisitor
        if not IsConstExprVisitor().is_const(sub.rhs):
            return None
        try:
            return int(sub.rhs.val())
        except Exception:
            return None

    def _indexed_ref_is_const(self, e):
        """True iff an indexed/subscript reference chain resolves to a fixed field
        — every subscript index along the chain is a constant — so ``get_target()``
        / ``subscript()`` yield the correct element without reading a stale rand
        value."""
        from vsc.model.expr_indexed_field_ref_model import ExprIndexedFieldRefModel
        from vsc.model.expr_array_subscript_model import ExprArraySubscriptModel
        node = e
        while True:
            if isinstance(node, ExprArraySubscriptModel):
                if self._const_subscript_index(node) is None:
                    return False
                node = node.lhs
            elif isinstance(node, ExprIndexedFieldRefModel):
                node = node.root
            elif isinstance(node, ExprFieldRefModel):
                return True
            else:
                return False

    # The variable-indexed-select element cap. The ITE-chain encoding is O(n)
    # nodes; cap it so a pathologically large rand array defers (retained)
    # rather than emit an unbounded chain.
    _MAX_SELECT_ELEMS = 1024

    # Native `expr_array_select` element cap (Workstream B). The C compiler's
    # EXPR_ARRAY_SELECT path (zsp_compile.c) builds flat guard-reified
    # propagators; benchmarking showed it beats the ITE chain up to ~64 elements
    # and degrades past ~96 (its 2n guard propagators fire poorly at scale, and
    # the freed element set nears MAX_DECISION_DEPTH). Above this the ITE chain is
    # both faster and correct (see the propagator side-table fix), so cap here.
    _NATIVE_SELECT_MAX = 64

    def _try_native_array_select(self, e, arr, n, w, signed):
        """Emit the native ``expr_array_select`` for ``arr[idx]`` when the array's
        elements are all rand vars with **contiguous** var-ids (base..base+n-1).

        This replaces the O(n) Python ITE chain with a single builder op that the
        C compiler lowers to flat, parallel guard-reified propagators — cheaper to
        build and better-propagating than the nested-ITE encoding, and it tightens
        ``idx`` to ``[0, n-1]`` itself (implicit in-range bound). Returns the
        result aux's var ref on success, or ``None`` to fall back to the ITE
        chain (non-contiguous / non-rand elements, or an index that can't be
        lowered to a plain var)."""
        m = self._m
        field_l = arr.field_l
        if not m.has(field_l[0]):
            return None
        base = m.id_of(field_l[0])
        for i in range(n):
            f = field_l[i]
            if not m.has(f) or m.id_of(f) != base + i:
                return None  # non-contiguous or baked-const element -> ITE path
        # The index must lower to a plain solver var (expr_array_select's `index`
        # is read via _is_var on the C side). A plain rand-field index already
        # is one; anything else is materialized, and if it can't be sized into an
        # aux we fall back rather than emit a select the compiler would drop.
        try:
            idx_w = int(e.rhs.width())
        except Exception:
            return None
        if not (self._AUX_MIN_W <= idx_w <= self._AUX_MAX_W):
            return None
        idx_ref = self.translate(e.rhs, want_var=True)
        if not self._last_simple:
            idx_ref = self._materialize(idx_ref, idx_w, bool(e.rhs.is_signed()))
        result_ref = self._new_aux(w, signed)
        self._b.add_constraint(self._b.expr_array_select(base, n, result_ref, idx_ref))
        return result_ref

    def visit_expr_array_subscript(self, e):
        if self._const_subscript_index(e) is not None:
            # Constant index -> the concrete element field (var if rand, else const).
            self._result = self._ref_for_field(e.subscript())
            self._last_simple = True
            return
        # Variable (rand) index: encode arr[idx] as an ITE chain over the active
        # element set (EF-1a):
        #   ITE(idx==0, arr[0], ITE(idx==1, arr[1], ... arr[n-1]))
        # built directly with the native ite so it composes in any enclosing
        # context (`arr[idx]==v`, `arr[idx] < arr[j]`).
        #
        # Why this is correct (and *more* correct than Boolector). pyvsc models a
        # subscript by snapshotting the index at constraint-build time
        # (ExprArraySubscriptModel.build reads int(rhs.val())) and registers only
        # arr[snapshot] as a rand var in the RandSet — the other elements (and a
        # co-solved index) are baked as constants reflecting their *current* values.
        # The ITE handles every resulting shape uniformly:
        #   * index resolved (const arm): the chain folds to the one selected
        #     element, exactly as Boolector's snapshot does;
        #   * index co-solved (var arm): the chain selects symbolically, so idx and
        #     the element move together — which Boolector gets *wrong* (it freezes
        #     idx at the stale snapshot, producing arr[stale]==v while reporting a
        #     different idx). The const arms still carry the unmapped elements'
        #     actual (unchanged) values, so the model stays self-consistent.
        # XCHECK agrees because it runs *after* the solve, when idx is concrete:
        # Boolector then builds arr[idx_final] and validates dv-solve's model.
        if not isinstance(e.lhs, ExprFieldRefModel) \
                or not isinstance(e.lhs.fm, FieldArrayModel):
            # Nested/object-array subscript chains are not in scope here.
            raise BackendIncomplete(
                "dv-solve: variable-indexed subscript over a non-array lvalue",
                reason_code="array")
        arr = e.lhs.fm
        n = self._array_elem_count(arr)
        if n < 1:
            raise BackendIncomplete(
                "dv-solve: variable-indexed select over an empty array",
                reason_code="array")
        if n > self._MAX_SELECT_ELEMS:
            raise BackendIncomplete(
                "dv-solve: variable-indexed select over %d elements exceeds the "
                "native %d-element cap" % (n, self._MAX_SELECT_ELEMS),
                reason_code="array")
        # Element width/sign come from the homogeneous element type.
        elem0 = arr.field_l[0]
        w = int(elem0.width)
        signed = bool(elem0.is_signed)
        # Native fast path (Workstream B): a contiguous all-rand element block of
        # a supported size compiles to a single flat guard-reified select instead
        # of the O(n) ITE chain below. Falls through on non-contiguous / oversized
        # arrays or a non-lowerable index.
        if self._AUX_MIN_W <= w <= self._AUX_MAX_W \
                and 2 <= n <= self._NATIVE_SELECT_MAX:
            native = self._try_native_array_select(e, arr, n, w, signed)
            if native is not None:
                self._result = native
                self._last_simple = True
                return
        # Index as a plain operand for the equality conditions.
        idx_ref = self.translate(e.rhs, want_var=True)
        idx_signed = bool(e.rhs.is_signed())
        elem_refs = [self._ref_for_field(arr.field_l[i]) for i in range(n)]
        # Fold right-to-left: element 0 is the outermost ITE condition; the final
        # else is arr[n-1] (reached when idx==n-1, or — if the model leaves idx
        # unbounded — any idx>=n-1; the realistic corpus bounds idx in range,
        # exactly as Boolector requires to avoid an index error).
        chain = elem_refs[n - 1]
        for i in range(n - 2, -1, -1):
            cond = self._b.expr_binary(
                BIN_EQ, idx_ref, self._b.expr_const(i, idx_signed))
            chain = self._b.expr_ite(cond, elem_refs[i], chain)
        if self._want_var and self._AUX_MIN_W <= w <= self._AUX_MAX_W:
            self._result = self._materialize(chain, w, signed)
            self._last_simple = True
        else:
            self._result = chain
            self._last_simple = False

    def visit_expr_indexed_fieldref(self, e):
        if self._indexed_ref_is_const(e):
            # Fixed path -> the concrete target field.
            self._result = self._ref_for_field(e.get_target())
            self._last_simple = True
            return
        raise BackendIncomplete(
            "dv-solve: variable-indexed object-array reference (Phase C-1)",
            reason_code="array")

    # ------------------------------------------------------------------ #
    # Bit-select expression (native via flattening)                        #
    # ------------------------------------------------------------------ #

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
            "dv-solve translator does not yet handle %s" % type(node).__name__,
            reason_code="translator-unsupported")

    # Composite / structural
    visit_composite_field = _unsupported
    visit_generator = _unsupported
    visit_field_scalar_array = _unsupported
    # Dist (native support arrives in Phase 2)
    visit_constraint_dist = _unsupported
    visit_dist_weight = _unsupported
    # Arrays / foreach (pre-expanded; residuals -> Phase 2)
    visit_constraint_foreach = _unsupported
    visit_constraint_unique_vec = _unsupported
    # An array/foreach inline scope (ArrayConstraintBuilder's expansion) is a
    # conjunction of per-element constraints — conjoin them exactly like an
    # ordinary scope. Any *soft* per-element constraint inside drops to nothing in
    # this hard context (visit_constraint_soft) and is enforced via the native soft
    # list instead, mirroring Boolector's `build(soft=False)` (SC-1).
    visit_constraint_inline_scope = visit_constraint_scope
    # Expression forms still routed to fallback
    visit_expr_dynamic = _unsupported
    visit_expr_range = _unsupported
    visit_expr_rangelist = _unsupported
