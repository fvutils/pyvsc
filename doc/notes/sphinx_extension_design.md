# `vsc.sphinx` — Sphinx support for documenting pyvsc classes

Status: **phase 1 implemented (§14); elaboration from phase 2 implemented
(§15)** · drafted 2026-10-13, reviewed 2026-10-13 (decisions in §13) ·
initial support scope.

Scope: a Sphinx extension that documents pyvsc random classes and covergroups as
what they are — fields with widths and domains, constraints, coverpoints, bins,
crosses — instead of as plain Python classes with odd attributes. The
**dataclass front-end (`vsc.dc` / `vdc`) is the primary target**. The classic
`@vsc.randobj` / `@vsc.covergroup` front-end is covered as far as it can be
without running user constructors (§9).

---

## 1. Why

pyvsc classes already carry structured metadata that matters to a reader. Plain
autodoc either drops it or renders it badly. For `examples/dc/01_alu_txn.py` and
`examples/dc/04_coverage.py` today:

| What the reader needs | What plain autodoc shows |
|---|---|
| `op` is a 4-bit unsigned **rand** field | `op: Annotated[int, _Width(4, unsigned)] = 0` |
| `c_op` is a **constraint**, and what it constrains | `c_op(self)`, a method with no body |
| `c_sel` is a **generic** constraint that takes `n` | `c_sel(self, n)`, a method |
| `mode` is a **push coverpoint** on `u2` with bins `lo=[0,1]`, `hi=[2,3]` | `<vsc.dc.coverage.descriptors._CPDescriptor object at 0x…>` |
| `op_x_mode` **crosses** `op` × `mode` | another descriptor repr |
| `AluCov.sample(op: Op, mode: int)` | not shown; the synthesized `sample` exists only on the subclass |
| The `__init__` signature takes `op`, `a`, `b` as kw-only | correct, but with the `Annotated[...]` noise |

(Checked with `inspect.signature` and `repr` on the example classes; these are
what autodoc formats.)

The information to do better is all computed already at decoration time and
cached on the class (§2). It needs a reader.

---

## 2. What pyvsc exposes (dataclass form)

Everything below is available **after import, without instantiating the class**,
because `@vdc.dataclass` elaborates once per type.

### 2.1 `RandClass` → `cls._vsc_type_model` (`vsc/dc/type_model.py`)

`TypeModel.fields: list[FieldDecl]`, in dataclass field order (bases first):

| `FieldDecl` attribute | Documentation use |
|---|---|
| `name` | member name |
| `bits`, `signed` | `u4` / `s16` / "4-bit unsigned"; element type for arrays |
| `rand_kind` (`"rand"`, `"randc"`, `""`) | badge: rand / randc / state |
| `role` (`"cg_arg"`, `"sample_arg"` on covergroups) | coverage-formal badge |
| `domain: DeclaredDomain` (`ranges`, `weights`, `size`) | "domain: 1..15, 100..200" / weighted table |
| `is_array`, `size`, `max_size`, `is_rand_sz` | "array[8]", "random-size array, ≤ 16" |
| `enum_cls` | type link to the enum |
| `is_composite`, `comp_cls`, `elem_comp_cls` | type link to the nested class |
| `soft` | "soft default: N" |
| `is_opaque` | plain Python state, solver ignores it — render as a normal attribute |

The original annotation (`vdc.u4`) and the `dataclasses.Field` default /
default-factory are on the class as usual.

`TypeModel.constraints: list[ConstraintProgram]` (fixed) and
`TypeModel.generic_constraints: dict[str, ConstraintProgram]` (generic and value),
collected across the MRO with subclass overrides winning:

| `ConstraintProgram` | Documentation use |
|---|---|
| `name` | member name |
| `kind` (`fixed` / `generic` / `value`) — the *effective* kind (a fixed constraint with parameters becomes generic) | badge, grouping |
| `params`, `param_defaults` | signature for generics: `c_sel(n, lo=0)` |
| `stmts` / `ret` (IR) | walk for the **fields referenced** and the **generics referenced** |

The method itself is still a function on the class, so `__doc__`,
`inspect.getsource`, `__qualname__` (defining class) and line numbers are
available. The constraint parser already strips the docstring
(`constraint_parser.py:140`, "A docstring documents the constraint; it is not
part of it"), so a docstring on a constraint is the natural place for its prose.

Not stored, but cheap to derive: which class in the MRO defines each
constraint (the function's `__qualname__`), and whether it overrides a base
constraint of the same name.

### 2.2 `Covergroup` → `cls._vsc_cg_type_model` (`vsc/dc/coverage/type_model.py`)

| Source | Documentation use |
|---|---|
| `coverpoints: list[_CPDescriptor]`, in declaration order | one entry per coverpoint |
| `_CPDescriptor.is_push` / `ref` | push vs pull; `ref` lambda source as the sampled expression |
| `width`, `signed`, `enum_cls` (resolved from `Coverpoint[T]` / `cp_t`) | sampled type |
| `bins` (`dict[name, bin / bin_array / wildcard_bin]`) or `None` | bins table, or "auto bins from `Op`" / "auto, ≤ `auto_bin_max`" |
| `ignore_bins`, `illegal_bins` | further tables |
| `iff` | guard expression (lambda source) |
| `options` | option overrides (weight, goal, at_least, auto_bin_max…) |
| `crosses: list[_CrossDescriptor]` | one entry per cross |
| `_CrossDescriptor.targets` (lambdas) | component coverpoints — resolved by name (§6.3) |
| cross `ignore_bins` / `illegal_bins` (lambdas returning a `binsof` tree) | rendered as `binsof(src).intersect([(0, 63)]) & …` (§6.3) |
| `sample_formals`, `sample_param_spec` | the synthesized `sample(op: Op, mode: int)` signature |
| `cg_arg` / `sample_arg` fields | "Sampling inputs" section |

`bin`, `bin_array`, `wildcard_bin` are the classic classes; their constructor
arguments are kept (`range_l`, `nbins`, …), so a bins table can be produced
statically.

### 2.3 What has no home today

- **Docs for non-function members.** Fields, coverpoints and crosses are class
  attributes. Sphinx's source analyzer already picks up `#:` comments and a
  string literal after the assignment for any class attribute, so these work
  without an API change (§7).
- **Docs for individual bins.** Bins are dict entries; nothing captures a
  comment next to one. §7 proposes reading them from source, and optionally a
  `doc=` argument.

---

## 3. Prior art

Surveyed from the source of autodoc_pydantic 2.2.0, sphinxcontrib-pydantic
0.4.0, sphinx-toolbox 4.3.1 (`more_autodoc`), enum-tools 0.13.0, sphinx-click
6.2.0, sphinx-argparse 0.6.1, sphinx-autodoc-typehints 3.13.10, sphinx-autoapi
3.8.1, sphinxcontrib-httpdomain 2.2.0, sphinx-vhdl 0.2.2, sphinxcontrib-hdl-diagrams,
sphinx-jsonschema 1.19.2, erdantic 1.2.1, and Sphinx 9.1.0.

### 3.1 The constraint that shapes everything: Sphinx 9 autodoc

Sphinx 9 rewrote autodoc. `automodule` / `autoclass` now dispatch over a fixed
set of object types (module, class, function, method, attribute, …) and **never
consult documenters registered with `app.add_autodocumenter()`**. A custom
`Documenter` still gets its own `autoX` directive, but `automodule :members:`
will not route members to it. The old class-based path survives only behind
`autodoc_use_legacy_class_based = True`, which is slated for removal; the
tracking issue (sphinx-doc/sphinx#14089) names no replacement API for custom
object kinds.

What keeps working on every version: the autodoc **events**
(`autodoc-process-docstring`, `autodoc-process-signature`,
`autodoc-skip-member`, `autodoc-process-bases`) and ordinary directives.

Consequences seen in the wild: autodoc_pydantic (Documenter-based) is
unmaintained and broken on Sphinx 9; its successor sphinxcontrib-pydantic is
built on events plus standalone directives. sphinx-autodoc-typehints is
event-only and now requires Sphinx ≥ 9.1.

Python versions matter here too: Sphinx 9.0 needs Python ≥ 3.11 and 9.1 needs
≥ 3.12, while pyvsc supports 3.10. pyvsc users will be on Sphinx 7/8 *and* 9.

### 3.2 autodoc_pydantic (Sphinx ≤ 8) — the model to borrow from

- **Detection with fallback.** `PydanticModelDocumenter(ClassDocumenter)`,
  `PydanticFieldDocumenter(AttributeDocumenter)`,
  `PydanticValidatorDocumenter(MethodDocumenter)`; each `can_document_member`
  is `super()` plus a pydantic check, at `priority = base + 10`, so non-pydantic
  objects fall through to stock autodoc.
- **Object types in the `py` domain.** Description directives
  `py:pydantic_model` / `_field` / `_validator` subclass `PyClasslike` /
  `PyAttribute` / `PyMethod`, added with `add_directive_to_domain("py", …)`.
  Object types are injected via
  `app.registry.domain_object_types.setdefault("py", {})[…] = ObjType(...)`
  (there is no public API for this); models also answer the `class` role, so
  `:py:class:` / `:py:obj:` resolve. An `object-description-transform` handler
  adds the stock CSS class (`class`, `attribute`, `method`) beside
  `pydantic_*` so themes style the output.
- **Grouping.** `member_order` 0 for fields, 50 for validators, with
  `groupwise` as the default order: fields, validators, everything else.
- **Summaries.** Model content opens with `:Fields:` and `:Validators:` field
  lists — one xref per member, validators shown as `validator » field`.
  Source order from `ModuleAnalyzer.tagorder`.
- **Bidirectional links.** A `ReferenceInspector` builds
  `ValidatorFieldMap(field, validator)` tuples once per model. Fields get
  "Validated by:"; validators get the validated fields **in the signature
  line** (` » field_a, field_b` as `pending_xref`s, parameter list removed).
- **Options.** Every option exists twice: `autodoc_pydantic_<objtype>_<name>`
  in `conf.py` (`rebuild="env"`) and `:<objtype>-<name>:` on the directive,
  resolved by one function (directive first, then config). The model
  directive also accepts its children's options and forwards them.
- **Inheritance.** Summaries list non-inherited members unless
  `:inherited-members:`; references to an inherited validator are rewritten
  from `Base.v` to `Child.v` when rendered on the child.
- **Generated blocks.** JSON schema and erdantic diagrams are generated as
  reST (`.. code-block:: json`, `.. graphviz::`), optionally wrapped in a
  collapsible raw-HTML `<details>`.

### 3.3 sphinxcontrib-pydantic (Sphinx 9) — the wiring to borrow

- `autodoc-process-docstring`: for a model class, append field/validator
  summaries and schema reST to `lines`; for an attribute, append description,
  constraints, "Validated by".
- `autodoc-process-signature`: return `("", ret)` to hide the parameter list.
- `autodoc-skip-member`: hide pydantic internals.
- Standalone `pydantic-model` / `autopydantic-model` directives build `desc`
  nodes, call `domain.note_object(...)`, and `nested_parse` generated text.
- Output uses stock `py:class` / `py:attribute` types; an opt-in hook
  re-registers the old `pydantic_*` object types so old intersphinx inventories
  still resolve.

### 3.4 Others, briefly

- **sphinx-toolbox `more_autodoc`** (TypedDict, NamedTuple, Protocol) and
  **enum_tools `autoenum`**: same pattern as autodoc_pydantic — `py` object
  types (`typeddict`, `enum`, `flag`), `add_role_to_domain("py", …)`,
  documenters that reorder members into sections (`:Required Keys:`; enum
  members in definition order). Toolbox notes that on Sphinx 9 the
  registration has to move into a `config-inited` handler.
- **sphinx-click**: one directive; introspects, generates reST line by line,
  `nested_parse`s it. Defines its **own events**
  (`sphinx-click-process-options`, `-usage`, …) so users can rewrite each
  generated section — a good customization hook.
- **sphinx-argparse**, **sphinxcontrib-httpdomain**: full custom domains with
  per-kind `XRefRole`s, `Index` subclasses for dedicated index pages
  ("routing table"), correct `clear_doc` / `merge_domaindata`. httpdomain
  keeps introspection (`autohttp` for flask/tornado) separate from the
  describing domain: the auto part *emits* `.. http:get::` reST.
- **sphinx-vhdl**: an HDL domain with `vhdl:entity` and `vhdl:autoentity`.
  A cautionary example — writes `env.domaindata` directly with no
  `clear_doc`/`merge_domaindata`, so not safe for parallel or incremental
  builds.
- **sphinxcontrib-hdl-diagrams**: a directive that shells out to
  yosys/netlistsvg and emits a custom node.
- **sphinx-autoapi**: parses source statically (astroid), templates per type;
  no hook for new object kinds. Being import-free, it cannot see pyvsc's
  decoration-time structure — not a base for this.
- **erdantic**: a plugin registry (`register_plugin(key, predicate,
  get_fields)`) with dataclass/attrs/pydantic built-ins; emits DOT. A pyvsc
  plugin would give composition diagrams nearly free.
- **Source display**: none of them render method bodies inline; they rely on
  `viewcode` links or `literalinclude :pyobject:`. Showing constraint bodies
  (§6.2) is new territory, done with the same "generate a `code-block`"
  technique autodoc_pydantic uses for JSON.

### 3.5 What we take

1. A Sphinx-free **inspector** with a reference map (constraint ↔ field,
   cross ↔ coverpoint), built once per class (autodoc_pydantic's
   `ModelInspector` / `ReferenceInspector`).
2. **Events + directives** as the wiring, not Documenters (§5.3) — the only
   approach that works across Sphinx 7, 8 and 9.
3. **`py`-domain object types** with stock-CSS fallback classes.
4. Renderers that produce **reST lines**, usable from an event (`lines.extend`)
   and from a directive (`nested_parse`) alike.
5. The **two-form option scheme**, with one resolver.
6. **Grouped members, summaries, bidirectional links**, inheritance-aware.
7. **Own events** for user rewriting of generated sections (sphinx-click).

---

## 4. Goals and non-goals

Goals (initial support):

1. `automodule` / `autoclass` on a module containing `vdc` classes produces
   pyvsc-aware output with **no per-class directives**, on Sphinx 7, 8 and 9
   (§5.3).
2. Constraints, fields, coverpoints and crosses are **first-class described
   objects**: each has an anchor, an index entry and a cross-reference role.
3. Fields and constraints cross-link: a field lists the constraints that read
   it; a constraint lists the fields it reads and the generics it references;
   a generic lists who references it.
4. Covergroups show the `sample()` signature, sampling inputs, a bins table per
   coverpoint, and the components and exclusions of each cross.
5. Everything is controllable globally from `conf.py` and per directive, with
   one naming scheme.
6. The introspection layer is independent of Sphinx and unit-testable.

Non-goals (initial support):

- A pretty-printer from constraint IR back to SystemVerilog-like text. The
  source *is* the readable form; we show it (§6.2).
- Diagrams. Designed for (§10), not in the first cut.
- Documenting classic classes whose fields exist only after `__init__` runs,
  beyond an opt-in (§9).
- Coverage *results* (hit counts). That is pyucis's job.

---

## 5. Architecture

```
vsc/sphinx/
    __init__.py        setup(app): config values, directives, event handlers
    introspect.py      pyvsc class -> plain description objects (no Sphinx import)
    render.py          description objects -> reST lines
    events.py          autodoc-process-docstring / -signature / -skip-member handlers
    directives.py      autorandclass/autocovergroup + py:randclass etc. (ObjectDescription)
    domain.py          object types + roles registered on the Python domain
```

Enabled with `extensions = ["vsc.sphinx"]`. Sphinx becomes an optional
dependency (`pyvsc[docs]`); `import vsc` never imports Sphinx.

**In-tree, not a separate package.** The introspection reads `TypeModel`,
`ConstraintProgram`, `_CPDescriptor` — internal classes that are still moving
(see `vdc_value_representation_plan.md`). Shipping the reader with the thing it
reads keeps them in lockstep, and the tests run in the same CI.

### 5.1 Introspection layer (`introspect.py`)

One function per kind, returning frozen dataclasses:

```python
describe_randclass(cls)  -> RandClassDesc(fields, constraints, generics, constants, bases)
describe_covergroup(cls) -> CovergroupDesc(coverpoints, crosses, sample_sig, inputs)

FieldDesc(name, owner, type_str, bits, signed, kind, domain, array, enum_cls,
          comp_cls, default, soft, constrained_by: list[str])
ConstraintDesc(name, owner, kind, params, defaults, doc, source, lineno,
               fields_read: list[str], generics_used: list[str],
               used_by: list[str], overrides: Optional[type])
CoverpointDesc(name, owner, push, type_str, ref_src, iff_src, bins: list[BinDesc],
               auto_bins: Optional[str], ignore: list[BinDesc], illegal: list[BinDesc],
               options: dict, crossed_by: list[str])
BinDesc(name, kind, values_str, count, doc)
CrossDesc(name, owner, components: list[str], ignore: list[CrossSelDesc],
          illegal: list[CrossSelDesc], options: dict)
```

Field/constraint links come from one IR walk per program: collect `IRField.path[0]`
(the top-level field; `path` for nested composite references gives the
"reads `sub.x`" detail) and `IRConstraintRef.name`. `type_model.py` already has
`_walk_refs` / `_refs_in_expr` for constraint references; the field walk is the
same traversal. **Proposal:** add a public `fields_read(prog)` and
`refs_used(prog)` to `constraint_ir.py` so the walker lives next to the IR and is
kept up to date when nodes are added, rather than a copy in the extension.

Why a separate layer: it is the part most likely to break as internals change,
and it is the part worth testing exhaustively. It can also feed other outputs
later (a JSON dump, a Markdown summary, an LLM-facing class description) at no
extra cost.

### 5.2 Where documented objects live: the Python domain

Two options:

- **A new `vsc` domain** (`.. vsc:constraint::`, `:vsc:constraint:`), like
  sphinxcontrib-httpdomain.
- **New object types on the existing `py` domain**, as autodoc_pydantic does
  (`py:pydantic_model`, `py:pydantic_field`).

**Recommendation: the `py` domain.** Constraints and coverpoints *are* Python
attributes with dotted names (`pkg.AluTxn.c_op`). Staying in `py` means
`:py:obj:`, `:py:attr:` and intersphinx resolve them with no extra work, the
objects sit in the normal module/class nesting, and `default_role = "any"`
(which this project's `conf.py` sets) finds them.

Registered directive/object types:

| Directive | objtype | Object |
|---|---|---|
| `py:randclass` | `randclass` | `RandClass` subclass |
| `py:randfield` | `randfield` | field of a rand class or covergroup |
| `py:constraint` | `constraint` | constraint method (any kind) |
| `py:covergroup` | `covergroup` | `Covergroup` subclass |
| `py:coverpoint` | `coverpoint` | coverpoint |
| `py:cross` | `cross` | cross |

Each also answers the stock roles (`randclass`/`covergroup` → `class`;
`randfield`/`coverpoint`/`cross` → `attr`; `constraint` → `meth`), so
`:py:obj:`, `:py:class:`, `:py:attr:`, `:py:meth:` all resolve, and we add role
aliases `:py:constraint:`, `:py:coverpoint:`, `:py:cross:`, `:py:randfield:`.

Registration follows autodoc_pydantic and sphinx-toolbox (§3.2, §3.4):
`app.add_directive_to_domain("py", ...)`,
`app.add_role_to_domain("py", ..., PyXRefRole())`, and `ObjType` entries
injected via `app.registry.domain_object_types["py"]` — there is no public
API for the last, which is why it is the step to prototype first (§13, #1). On
Sphinx 9 it has to run in a `config-inited` handler rather than in `setup()`.
An `object-description-transform` handler adds the stock CSS class
(`class`/`attribute`/`method`) beside ours so existing themes style the
entries; a small CSS file styles the badges. Fallback if the injection proves
brittle: a thin `vsc` domain whose roles delegate unresolved targets to `py`.

A dedicated index page ("Constraints", "Coverpoints"), as httpdomain and
sphinx-argparse provide, would need our own domain (`Index` subclasses live
on a domain). Not in phase 1; it is the main argument for the fallback
domain if one is later wanted.

### 5.3 Wiring: autodoc events plus own directives (no Documenters)

Because Sphinx 9 no longer routes `automodule` members to custom
Documenters (§3.1), and pyvsc users span Sphinx 7–9 (§3.1), the extension
uses **one wiring path that works on all of them**: autodoc events, plus its
own directives. It does not subclass `Documenter`.

**Inside `automodule` / `autoclass`** (zero per-class markup — goal 1):

| Event | Handler |
|---|---|
| `autodoc-process-docstring`, `what == "class"`, obj is a vdc `RandClass` / `Covergroup` | Append the generated reST to `lines`: summary, then a rubric per group with nested `.. py:randfield::`, `.. py:constraint::`, `.. py:coverpoint::`, `.. py:cross::` blocks. Nested inside the class's content, they get the class as their parent, so their full names are `pkg.AluTxn.c_op`. |
| `autodoc-skip-member` | Skip every member we rendered (fields, constraint methods, coverpoint/cross descriptors, the synthesized `sample`), so autodoc does not document them a second time; skip `RandClass` / `Covergroup` machinery (`randomize`, `set_rand_mode`, …) always (§13, #5). Everything else — ordinary methods, properties, `pre_randomize`/`post_randomize` — flows through stock autodoc after our groups. |
| `autodoc-process-signature` | Rewrite `Annotated[int, _Width(4, unsigned)]` to `u4` in any signature (class `__init__`, and ordinary functions taking `vdc.u8`); hide the synthesized `__init__` parameter list if `vsc_randclass_hide_paramlist`; for classic interposer classes, take the signature from the user's class (§9). |
| `autodoc-process-docstring`, `what == "attribute"` on a vdc field or descriptor | Best-effort: when a user writes `autoattribute AluTxn.op` by hand, append the field details. |

`autoclass_content = "both"` (this project's setting) concatenates class and
`__init__` docstrings before the event fires; the handler appends after both,
once per class.

**Own directives** (`directives.py`), for when per-object options are needed —
the events above can only read `conf.py` values:

- `.. autorandclass:: pkg.AluTxn` / `.. autocovergroup:: pkg.AddrCov` —
  import the object, run the inspector and renderer, and `nested_parse` a
  `.. py:randclass::` block. Accept every §8 option, including the children's
  (`:constraint-show-source: none` on the class applies to its constraints).
  Also accept `:members:` / `:exclude-members:` to restrict which fields and
  constraints appear.
- `.. py:randclass::`, `py:randfield`, `py:constraint`, `py:covergroup`,
  `py:coverpoint`, `py:cross` — `ObjectDescription` subclasses of
  `PyClasslike` / `PyAttribute` / `PyMethod`, usable by hand in prose (e.g.
  describing a constraint in a design note) and emitted by everything above.
  Their options carry the rendered facts (`:kind:`, `:type:`, `:domain:`,
  `:reads:`, `:used-by:`…), so the generated reST is plain and readable when
  debugged.

**Why not Documenters, even optionally for Sphinx ≤ 8.** They would give
`automodule` native per-member dispatch on old Sphinx only, at the cost of a
second code path that dead-ends on Sphinx 9. The event path gives the same
output on every version. Revisit only if Sphinx grows a public API for custom
object kinds (sphinx-doc/sphinx#14089).

**Rendering is reST lines.** `render.py` turns description objects into
lists of reST lines. The event handler extends `lines` with them; the
directives `nested_parse` them. One renderer, two entry points.

**User hooks.** Like sphinx-click, emit our own events before each section is
appended — `vsc-process-field`, `vsc-process-constraint`,
`vsc-process-coverpoint`, `vsc-process-cross` (args: app, description
object, lines) — so a project can rewrite or extend a section without forking
the extension. Phase 2.

**Build safety.** All cross-link data (constraint ↔ field, cross ↔ coverpoint)
comes from the inspector at render time, not from `env` storage; targets are
registered through the `py` domain, which already implements
`clear_doc`/`merge_domaindata`. So the extension declares
`parallel_read_safe = True` and holds no env state of its own (avoiding
sphinx-vhdl's mistake, §3.4).

**Inheritance.** A field or constraint defined on a user base class is
rendered on the subclass when `:inherited-members:` is set, with "inherited
from `Base`"; links to it point at the subclass entry (autodoc_pydantic's
reference rewriting). Without the option, the subclass page lists inherited
names in the summary with links to the base's entries. Inheritance always stops
at `RandClass` / `Covergroup` — their methods are machinery, not the user's API.

---

## 6. Rendering

Sketched as the reST the renderer generates, then how it reads.

### 6.1 Rand class and fields

```python
@vdc.dataclass
class AluTxn(vdc.RandClass):
    """An ALU transaction."""

    op: vdc.u4 = vdc.rand()            #: Operation select.
    a:  vdc.u32 = vdc.rand(domain=(1, 1000))
    """First operand."""
    b:  vdc.u32 = vdc.rand()
    tags: list[vdc.u8] = vdc.rand(max_size=4)
```

Generated:

```rst
.. py:randclass:: AluTxn(*, op: u4 = 0, a: u32 = 0, b: u32 = 0, tags: list[u8] = [])
   :module: alu

   An ALU transaction.

   .. rubric:: Fields

   ========  ======  ======  ==============================  ===================
   Field     Type    Kind    Domain / size                   Constrained by
   ========  ======  ======  ==============================  ===================
   op_       u4      rand                                    c_op_
   a_        u32     rand    1..1000                         c_op_
   b_        u32     rand                                    c_op_
   tags_     u8[]    rand    random size, ≤ 4
   ========  ======  ======  ==============================  ===================

   .. py:randfield:: op
      :type: u4
      :kind: rand
      :constrained-by: c_op

      Operation select.
   ...
```

Rendered per field (the long form):

> **rand** op: u4 — 4-bit unsigned
> Operation select.
> *Constrained by:* `c_op`

Type rendering: `uN`/`sN` for width aliases; the enum class as a link for enum
fields; the nested class as a link for composites; `T[N]` for fixed arrays,
`T[]` for random-size arrays with the `max_size` noted. Domains print from
`DeclaredDomain.ranges` as `lo..hi` items, with a weight column when weighted.

### 6.2 Constraints

```python
    @vdc.constraint
    def c_op(self):
        """Keep op to the eight real operations; operands ascending."""
        self.op <= 7
        self.a < self.b

    @vdc.constraint.generic
    def c_small(self, n=16):
        """Both operands below *n*."""
        self.a < n
        self.b < n
```

Generated:

```rst
   .. rubric:: Constraints

   .. py:constraint:: c_op
      :kind: fixed
      :fields: op, a, b

      Keep op to the eight real operations; operands ascending.

      .. code-block:: python

         self.op <= 7
         self.a < self.b

   .. rubric:: Generic constraints

   .. py:constraint:: c_small(n=16)
      :kind: generic
      :fields: a, b
      :used-by: c_op

      Both operands below *n*.
      ...
```

Rendered:

> **constraint** c_op
> Keep op to the eight real operations; operands ascending.
> ```
> self.op <= 7
> self.a < self.b
> ```
> *Reads:* `op`, `a`, `b`

> **generic constraint** c_small(n=16)
> Both operands below *n*.
> *Reads:* `a`, `b` · *Referenced by:* `c_op`

Choices:

- **Body, not signature.** A constraint's meaning is its body. The default is
  to show the body (decorator, `def` line and docstring removed, dedented) as a
  `code-block`. `vsc_constraint_show_source = "body" | "collapsed" | "none"`;
  `collapsed` uses a `<details>` wrapper in HTML and the full block elsewhere.
- **Kind is a badge and a group.** Fixed, generic and value constraints are
  separate groups because the reader's question differs: "what always holds"
  vs "what is available to compose".
- **Signature only for generics/values**, since a fixed constraint takes no
  arguments; `self` is never shown.
- **Overrides** are noted: "Overrides `Base.c_op`" when a subclass redefines a
  base constraint, and a warning badge when the kind changes (the case
  `type_model.py` already warns about).
- **Class constants folded per subclass** (`examples/dc/11_class_constants.py`)
  are not expanded in the body — the source is shown as written. A subclass
  that changes a constant the inherited constraint reads gets a note: "`MAX_LEN`
  = 256 here (inherited `c` reads it)". This is cheap: the constants a program
  reads are visible in the IR before folding. Phase 2.
- **Control methods** (`set_constraint_mode`, `set_rand_mode`) are not
  repeated per constraint; the class entry can add one line pointing at
  them (`vsc_randclass_show_mode_hint`, off by default).

### 6.3 Covergroups, coverpoints, crosses

```python
@vdc.dataclass
class AddrCov(vdc.Covergroup):
    """Address coverage for the DMA engine."""
    src: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
        bins=dict(s=vdc.bin_array([4], (0, 255))))
    dst: vdc.Coverpoint[vdc.u8] = vdc.coverpoint(
        bins=dict(d=vdc.bin_array([4], (0, 255))))
    src_x_dst: vdc.Cross = vdc.cross(
        lambda s: s.src, lambda s: s.dst,
        ignore_bins=dict(dontcare=lambda s: vdc.binsof(s.src).intersect([(0, 63)])
                                          & vdc.binsof(s.dst).intersect([(192, 255)])))
```

Rendered:

> **covergroup** AddrCov
> Address coverage for the DMA engine.
> **sample**(src: int, dst: int)
>
> **Coverpoints**
>
> **coverpoint** src: u8 — push (sample formal 1)
>
> | Bin | Kind | Values | Bins |
> |---|---|---|---|
> | s | bin_array | 0..255 | 4 |
>
> *Crossed by:* `src_x_dst`
>
> **Crosses**
>
> **cross** src_x_dst = `src` × `dst`
>
> | Ignore | Selection |
> |---|---|
> | dontcare | `binsof(src).intersect([(0, 63)]) & binsof(dst).intersect([(192, 255)])` |

How each piece is obtained without instantiating the covergroup:

- **Sample signature**: `sample_param_spec`, the same data that builds the
  synthesized `sample()`; rendered with enum annotations linked.
- **Pull coverpoint expression and `iff`**: the source text of the `ref=` /
  `iff=` lambda. Taken from an AST pass over the class source: find the
  assignment to the coverpoint name, take `ast.get_source_segment` of the
  keyword argument's lambda body. (`inspect.getsource` on a lambda returns the
  whole line, which is wrong for multi-line or shared lines.) The same pass
  gives the declaration line for "view source" links.
- **Cross components**: call each target lambda with a *probe* object whose
  attribute access returns a stand-in naming the attribute (`lambda s: s.op` →
  `"op"`). This is exact for every target form the runtime supports, without
  parsing lambdas.
- **Cross selections**: call the `ignore_bins` / `illegal_bins` lambdas with a
  probe whose attributes are stand-in `Coverpoint` objects (so `binsof`'s
  `isinstance` check passes), then print the resulting `_BinsofExpr` tree.
  Falls back to the lambda's source text if the call raises.
- **Auto bins**: "auto, one per member of `Op`" for an enum; "auto, 2^w
  values in ≤ `auto_bin_max` bins" for a width. The exact count needs the
  runtime model; see the elaboration option below.
- **Bin counts** for explicit bins come from the spec (`bin` = 1,
  `bin_array([n], …)` = n, `bin_array([], …)` = one per value).

**Optional elaboration.** `vsc_covergroup_elaborate = False` by default. When
true, the extension constructs one instance (`cls()`, `cg_arg`s default to
`None`) inside a try/except and reads exact bin counts, cross bin totals and
ignored/illegal counts (`n_bins`, `n_ignore`, `n_illegal`) from the runtime
model. Off by default because it runs user code (`__post_init__`, custom
`sample` set-up) at doc-build time, and a covergroup with a required `cg_arg`
may not construct.

### 6.4 Summaries

Each class can open with a compact summary (pydantic-style), configurable:

- rand class: the fields table of §6.1, and a one-line-per-constraint list
  (name, kind, first docstring line);
- covergroup: a table of coverpoints (name, type, push/pull, bin count) and
  crosses (name, components).

`vsc_randclass_summary = "table" | "list" | "none"` and the same for
covergroups.

---

## 7. Where the prose comes from

| Object | Source (in order) |
|---|---|
| Class | class docstring |
| Field, coverpoint, cross | `#:` comment above or on the line; string literal after the assignment (Sphinx's `ModuleAnalyzer`, already used for attribute docs) |
| Constraint | the method docstring |
| Bin | proposal below |

Fields, coverpoints and crosses therefore need **no API change**: the
attribute-doc conventions already work for class attributes, which is what
they are.

**Bins** are dict entries in a `bins=` / `ignore_bins=` argument, where no
existing convention applies. Two complementary options:

1. Read a trailing `#` comment on each dict entry from the source
   (`tokenize` over the coverpoint's source segment, matched to dict keys by
   line). Zero API change; covers the common style
   `lo=vdc.bin(0, 1),   # idle modes`.
2. Accept `doc="..."` on `vdc.bin`, `vdc.bin_array`, `vdc.wildcard_bin`
   (classic classes; one optional keyword, stored and ignored by coverage).

Decision (review): do **both** in phase 1. `doc=` wins when given; the
trailing comment is the fallback. The same `doc=` question applies to
`vdc.rand()`/`vdc.coverpoint()`, but the attribute-doc conventions already
cover those, so no.

---

## 8. Configuration

One naming scheme, autodoc_pydantic's: `vsc_<object>_<option>` in `conf.py`,
and `:<object>-<option>:` on a directive (`vsc_constraint_show_source` ↔
`:constraint-show-source:`). The object prefix stays on the directive form
because `autorandclass` / `autocovergroup` accept their children's options.
One resolver: directive option if given, else the `conf.py` value. Event-driven
output (plain `automodule`) can only see `conf.py` values; per-class overrides
need the `auto*` directives (§5.3).

| `conf.py` | Directive option | Default | Meaning |
|---|---|---|---|
| `vsc_autodoc_enable` | — | `True` | event handlers enrich `automodule`/`autoclass` output for pyvsc classes |
| `vsc_randclass_hide_paramlist` | `:randclass-hide-paramlist:` | `False` | drop the synthesized `__init__` parameters from the class signature (the fields table says it all) |
| `vsc_randclass_summary` | `:randclass-summary:` | `"table"` | fields table + constraint list at the top |
| `vsc_randclass_member_groups` | `:randclass-member-groups:` | `fields, constraints, generics, other` | group order |
| `vsc_randclass_show_mode_hint` | `:randclass-show-mode-hint:` | `False` | one line about `set_constraint_mode`/`set_rand_mode` |
| `vsc_field_show_constraints` | `:field-show-constraints:` | `True` | "Constrained by" on fields |
| `vsc_field_show_domain` | `:field-show-domain:` | `True` | |
| `vsc_constraint_show_source` | `:constraint-show-source:` | `"body"` | `body` / `collapsed` / `none` |
| `vsc_constraint_show_fields` | `:constraint-show-fields:` | `True` | "Reads" list |
| `vsc_constraint_signature_fields` | `:constraint-signature-fields:` | `False` | also show the fields read in the signature line, `c_op » op, a, b` (autodoc_pydantic's validator style) |
| `vsc_constraint_show_refs` | `:constraint-show-refs:` | `True` | generics used / used by |
| `vsc_covergroup_summary` | `:covergroup-summary:` | `"table"` | |
| `vsc_covergroup_elaborate` | `:covergroup-elaborate:` | `False` | instantiate for exact bin counts (§6.3) |
| `vsc_coverpoint_show_bins` | `:coverpoint-show-bins:` | `True` | bins / ignore / illegal tables |
| `vsc_coverpoint_show_options` | `:coverpoint-show-options:` | `True` | |
| `vsc_cross_show_selections` | `:cross-show-selections:` | `True` | binsof ignore/illegal |
| `vsc_type_style` | — | `"alias"` | `u4` vs `bit[3:0]` vs `4-bit unsigned` |
| `vsc_classic_instantiate` | `:classic-instantiate:` | `False` | §9 |

Registered with `app.add_config_value(..., "env")` so changing them rebuilds.

---

## 9. Classic front-end

What is visible on a classic `@vsc.randobj` class without instantiating it:

- **Constraints**: yes. `@vsc.constraint` / `@vsc.dynamic_constraint` replace
  the method with a `constraint_t` / `dynamic_constraint_t` class attribute
  wrapping the function in `.c` — docstring and source are on `.c`.
  The event handlers recognise these and document them like dc
  constraints (kind `fixed` / `dynamic`), showing the body. There is no IR, so
  no "Reads" list — unless we parse the body ourselves, which is out of scope.
- **Fields and coverpoints**: no. They are created in `__init__`
  (`self.a = vsc.rand_bit_t(8)`, `self.cp = vsc.coverpoint(...)`).
- **Signature**: the decorator returns an interposer subclass whose `__init__`
  is `(*args, **kwargs)`. It copies `__doc__`, `__module__`, `__qualname__`, so
  the class is found and named correctly, but the signature should be taken
  from the user's class (the interposer's base) — an
  `autodoc-process-signature` handler.

`vsc_classic_instantiate = True` (or `:instantiate:` per class) constructs one
instance with no arguments and reads fields (`_int_field_info`, the
`type_base` attributes) and coverpoints from it. Off by default for the same
reason as covergroup elaboration. Static recovery from the `__init__` AST
(recognising `self.x = vsc.rand_bit_t(8)`) is possible but brittle and is not
proposed.

So classic gets constraint documentation in phase 1 and opt-in field and
coverpoint documentation in phase 2.

---

## 10. Later: diagrams

Designed for, not in phase 1. All from the introspection layer, emitted as
graphviz (`sphinx.ext.graphviz`, which `conf.py` already configures for SVG):

- **Constraint graph**: bipartite fields ↔ constraints for one class. Shows
  at a glance which constraints couple which fields — the solve partitions a
  verification engineer worries about.
- **Composition diagram**: nested composites and arrays of composites, like
  erdantic's model diagrams.
- **Cross diagram**: coverpoints and the crosses over them.

Directive: `.. vsc-diagram:: pkg.AluTxn :kind: constraints`.

---

## 11. Testing

- **Introspection**: plain pytest over `examples/dc/*` and purpose-built
  fixtures — every `FieldDecl` shape (scalar, enum, composite, array, enum
  array, composite array, random-size, domain, weighted domain, bitv),
  every constraint kind, overrides, inheritance, class constants, push/pull
  coverpoints, auto bins, `bin_array`, `wildcard_bin`, crosses of crosses,
  `binsof` trees.
- **Sphinx output**: `sphinx.testing` (`SphinxTestApp`) builds a tiny project
  per case and asserts on the doctree (object types, ids, xref resolution) and
  on warnings (none). Golden HTML is avoided — too brittle across Sphinx and
  theme versions.
- **This project's docs**: the dataclass pages under `doc/source/dataclass/`
  get an "API" page built with the extension from `examples/dc/`, so the
  docs build in CI exercises it.
- Version matrix: Sphinx 7.x on Python 3.10, Sphinx 8.x on 3.11, Sphinx 9.x
  on 3.12 — the three autodoc regimes pyvsc users will actually have (§3.1).
  The same doctree assertions run on all three.

---

## 12. Phasing

**Phase 1 — useful on its own**

1. `introspect.py` for dc rand classes and covergroups; `fields_read` /
   `refs_used` added to `constraint_ir.py`.
2. Domain registration (object types, roles) — prototyped first, on Sphinx 7
   and 9 (§13, #1). Also confirm the event path end to end: a class docstring
   extended with nested `py:constraint` blocks resolves names and links
   correctly under `automodule` on both.
3. Event handlers + directives for rand class, field, constraint, covergroup,
   coverpoint, cross; member grouping; constraint body; field ↔ constraint
   links; bins tables; cross components and `binsof` selections; `sample()`
   signature.
4. Signature cleanup for width aliases.
5. Classic constraints.
6. Config values of §8 (except the elaboration/instantiation ones).
7. Bin docs: `doc=` on `bin` / `bin_array` / `wildcard_bin` (and
   `wildcard_bin_array`), plus trailing-comment extraction as fallback (§7).
8. Tests (§11) and an API page in this repo's docs.

**Phase 2**

- `vsc_covergroup_elaborate`, `vsc_classic_instantiate`.
- Class-constant notes on subclasses.
- Summaries for covergroups.
- User events (`vsc-process-constraint`, …) for rewriting generated sections.

**Phase 3**

- Diagrams.
- JSON/Markdown output from the introspection layer, if wanted.

---

## 13. Decisions (review, 2026-10-13)

| # | Question | Decision |
|---|---|---|
| 1 | `py` domain vs `vsc` domain | **`py` domain**, object types injected as autodoc_pydantic / sphinx-toolbox do; confirmed by the phase-1 prototype on Sphinx 7 and 9. No dedicated index pages for now. |
| 2 | Events-only wiring | **Accepted.** Plain `automodule` takes `conf.py` settings only; per-class options go through `autorandclass` / `autocovergroup`. |
| 3 | Constraint body: source vs normalized rendering | **Source as written.** No IR pretty-printer. |
| 4 | `doc=` on bins | **Yes, in phase 1**, with trailing-comment extraction as fallback (§7). |
| 5 | Inherited `RandClass` / `Covergroup` machinery | **Always hidden.** Inheritance stops at the pyvsc base classes; `pre_randomize` / `post_randomize` shown when the user class defines them. |
| 6 | Package name | **`vsc.sphinx`**, in-tree, Sphinx an optional dependency (`pyvsc[docs]`). |
| 7 | Running user code at doc time | **Acceptable as opt-in** (`vsc_covergroup_elaborate`, `vsc_classic_instantiate`), off by default. |

The original questions, kept for context:

1. **`py` domain vs `vsc` domain.** Recommendation is `py` (§5.2). Needs a
   prototype to confirm the object-type injection works on Sphinx 7–9
   (it is a private-registry hack that two maintained extensions rely on).
   Do we want dedicated Constraint/Coverpoint index pages, which would tip
   this toward a domain?
2. **Events-only wiring** (§5.3). The cost: plain `automodule` output can't
   take per-class options, only `conf.py` ones; per-class control needs
   `autorandclass`. Acceptable?
3. **Constraint body as source vs a normalized rendering.** Source is
   recommended. A rendering from the IR would allow SV-flavored output
   (`a inside {[1:15]}`) for SV readers; worth it?
4. **`doc=` on bins** (§7): wanted now, or only if comment extraction falls
   short?
5. **Inherited pyvsc machinery.** With `:inherited-members:` (needed to
   show fields/constraints from a user base class), autodoc would also pull
   in `randomize`, `randomize_with`, `set_rand_mode`, `sample`, … from
   `RandClass`/`Covergroup` on every page. Proposal: the handlers always
   stop inheritance at the pyvsc base classes; `pre_randomize` /
   `post_randomize` shown when the user class defines them.
6. **Package name**: `vsc.sphinx` (proposed) vs `vsc.sphinxext` vs a
   separate `sphinx-pyvsc` distribution. In-tree is recommended (§5).
7. **Elaborating at doc time** (§6.3, §9): acceptable as opt-in, or should
   we avoid running user code entirely?

---

## 14. Implementation status (phase 1, 2026-10-13)

Code: `src/vsc/sphinx/` (`introspect.py`, `render.py`, `domain.py`,
`events.py`, `directives.py`, `__init__.py`). Tests: `ve/unit_sphinx/`
(introspection without Sphinx; `SphinxTestApp` builds of three test roots).
User page: `doc/source/dataclass/documenting.rst`, built from
`doc/source/dataclass/dma_doc_example.py`; this repo's `conf.py` now loads the
extension. CI: a `ci-sphinx` job runs `ve/unit_sphinx` on Sphinx 7/Python
3.10, 8/3.11 and 9/3.12. `pyproject.toml` gains a `docs` extra.

Verified locally: the suite passes on Sphinx 7.4 (Python 3.10 and 3.12), 8.2
and 9.1, including 9.1 with `autodoc_use_legacy_class_based = True`, and with
no solver installed. A parallel (`-j 2`) build keeps the object types in the
inventory. This repo's docs build with no warnings on the dataclass pages and
no new warnings elsewhere.

**Prototype result (§13, #1).** Injecting object types through
`app.registry.domain_object_types["py"]` in `setup()` works on 7, 8 and 9; no
`config-inited` handler was needed (`create_domains` reads the registry when
the environment is created). The fallback domain was not needed.

**pyvsc changes outside `vsc.sphinx`:**

- `constraint_ir.py`: `iter_nodes(root)` (generic over `__slots__`),
  `fields_read(prog)`, `refs_used(prog)` (§5.1).
- `vsc/coverage.py`: `doc=` on `bin`, `bin_array`, `wildcard_bin`,
  `wildcard_bin_array`; each also keeps its constructor arguments as
  `spec_args`, because `bin_array.build_cov_model` intersects `self.ranges`
  in place when a covergroup is built (§7).

**Where the implementation differs from the design:**

1. **`autorandclass` / `autocovergroup` delegate to `autoclass`** rather than
   generating a `.. py:randclass::` block (§5.3). They push their options where
   the event handlers read them, then run whatever `autoclass` directive is
   registered. Output is therefore identical to the `automodule` path, with
   all of autoclass's options, on every Sphinx version.
2. **Class entries are retyped after parsing.** autodoc always writes
   `.. py:class::`; a `doctree-read` handler changes a pyvsc class's entry to
   `randclass` / `covergroup` (domain record, CSS classes, signature prefix,
   index text). The `py:randclass` / `py:covergroup` directives exist for hand
   use.
3. **`autodoc-skip-member` finds the class from autodoc's frame.** The event
   does not pass the parent class, and Sphinx 9 fires every
   `autodoc-process-docstring` for a module before filtering any members, so
   "the last class seen" is wrong there. `events._parent_class()` reads
   `props` (Sphinx 9) or the documenter `self` (Sphinx ≤ 8 and 9-legacy) from
   the filtering frame. This is the most version-sensitive piece; the
   tests cover all three regimes.
4. **Facts are directive options rendered as a field list**, placed after the
   prose and the constraint body and before generated tables (bins,
   selections).
5. **Width aliases in type positions** (`u4`, and the `sv` / `words`
   spellings) are resolved to plain text by a `missing-reference` handler,
   so `nitpicky` builds stay clean.
6. **Covergroup summaries** (planned for phase 2) were cheap and are in.
7. **`:members: a, b` / `:exclude-members:`** restrict the pyvsc members too.
   A reference to an excluded member is shown without a link (`!name`).
8. **An overriding constraint does not inherit the base's docstring**
   (`inspect.getdoc` would), since its body differs.
9. **No CSS file.** Stock CSS classes are added beside ours and the
   signature prefixes use the stock keyword nodes, so themes style the
   entries as they are.
10. `vsc_randclass_member_groups` orders only the pyvsc groups. autodoc's own
    members always follow them, because the event path cannot reorder
    autodoc's output.

**Not done in phase 1:** user events (`vsc-process-*`), elaboration
(`vsc_covergroup_elaborate`, `vsc_classic_instantiate`; done since, §15),
class-constant notes on subclasses, diagrams, JSON/Markdown output — all
phase 2/3 as planned.

**Found along the way (fixed separately):** a cross
`binsof(cp).intersect(...)` raised `TypeError: 'RangelistModel' object is not
iterable` (`coverpoint_cross_model.py:212`) when `cp` had a `vdc.bin(...)` /
`vsc.bin(...)` bin: `CoverpointBinSingleBagModel.get_bin_range` returned its
`RangelistModel` rather than a tuple of entries. It now returns entries like
the other bin models; the user page's example uses `vdc.bin((lo, hi))` again.

---

## 15. Elaboration (phase 2, 2026-10-13)

Code: `src/vsc/sphinx/elaborate.py` (Sphinx-free); wired in `events.py`
(`_describe(cls, elaborate, instantiate)`, cached per flag pair, and
`describe_for(app, cls)`, which reads the flags for the object being
documented). Tests: `ve/unit_sphinx/test_elaborate.py` (no Sphinx) and
`test_sphinx_elaborate.py` (builds of `roots/test-elab` and
`roots/test-elab-directive`), on the fixture `vsc_elab_fixture.py`. User
docs: "Exact counts and classic fields" on
`doc/source/dataclass/documenting.rst`; this repo's `conf.py` turns
`vsc_covergroup_elaborate` on for that page's example.

**`vsc_covergroup_elaborate`** (off by default, `:covergroup-elaborate:` per
class). Differs from §6.3 in one respect: the class is **not constructed**.
`Covergroup._build_runtime` was split into `_build_models()` (build and
finalize the coverpoint / cross models, return the `CovergroupModel`) and the
registration; elaboration calls `_build_models()` on `cls.__new__(cls)` with
each dataclass field set to its default. So `__init__` / `__post_init__` do
not run and nothing reaches the `CoverageRegistry`; the only user code run is
the cross target and selection lambdas, which the static path already calls
with a probe. Bins are class-level in the dc API, so the counts are those of
any instance (a test compares against a constructed one). A selection that
reads a `cg_arg` sees `None` and fails; the class is then documented
statically with a warning.

Facts added: per bin spec the number of bins after exclusions (0 shown as
"0 (all values excluded)"); coverpoint total (`:bins: 7`); automatic bins
as built ("64 bins of 4 values over 0..255", "3 bins of 85 to 87 values …",
"2 bins, one per member of Kind (1 excluded)"); per cross
`:bins: 14: 3 counted, 7 ignored, 4 illegal`, and a Bins column in the
covergroup's crosses table.

Since nothing user-visible runs any more, the reason given in §13 #7 for
keeping it off by default is much weaker. It stays off, as decided; turning it
on by default is a one-line change in `render.DEFAULTS`.

**`vsc_classic_instantiate`** (off by default, `:classic-instantiate:` per
class), as §9 proposed: `cls()` with no arguments, against a scratch
`CoverageRegistry` (swapped in and restored), so a documentation instance of a
classic covergroup is not registered.

- `@vsc.randobj`: fields from the instance's `vars()` — every value carrying
  `_int_field_info` (scalars, enums, `list_t` and its subclasses, nested
  randobjs via `rand_attr` / `attr`); kind from `is_rand`; type `u12` /
  enum / `u8[4]` / `u8[]` (+ size "random" for `randsz_list_t`) / class name;
  initial value when non-zero. The owner is the base-most user class whose
  `__init__` assigns `self.<name>` (`_ClassSource.self_assigns`), so a
  subclass documents only its own fields and its summary links to the base.
  `#:` comments on `self.x = …` come from Sphinx's analyzer, as for any
  instance attribute. Classic has no randc and no constraint IR, so there is
  no "Constrained by".
- `@vsc.covergroup`: now described (it was a plain class before). Statically:
  an empty `CovergroupDesc(classic=True)` — the entry is typed `covergroup` and
  the pyvsc methods are hidden. Instantiated: sampling inputs and `sample()`
  formals from `with_sample` (`CovergroupInt.sample_var_l` / `sample_obj_l`);
  coverpoints and crosses from `buildable_l` in declaration order, named by
  the instance attribute that holds them; sampled expression, `iff` and bin /
  selection comments from the `__init__` AST; bins from the same `vsc.bin*`
  specs as dc; counts from each object's `.model`. Classic cross selections
  are predicates over component bins, shown as written.

**Failures** raise `ElaborationError` (cause chained); `describe_for` falls
back to the static description and warns once per build per class and flag
pair, type `vsc`, subtype `elaborate` (`suppress_warnings =
["vsc.elaborate"]`).

**Fixed along the way:**

1. On Sphinx ≤ 8, `autorandclass` / `autocovergroup` / `autoclass` without
   `:members:` rendered none of the pyvsc members: autodoc passes
   `members=[]` there (9 passes `None`), which was read as "only these: none".
   Now an empty list means no restriction. The phase 1 test only checked
   something was *absent* in that case; it now checks the members are present.
2. A cross selection reading a non-coverpoint attribute
   (`intersect([(0, s.limit)])`) printed a stand-in object's repr. The probe
   now answers only coverpoint and cross names; anything else raises, and the
   selection is shown as written.

