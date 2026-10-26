
## 1.0.0

Boolector is still the default solver. pyvsc now also installs dv-solve, a new
native solver, which you opt in to with `vsc.set_solver_backend("dv-solve")` or
`VSC_SOLVER=dv-solve`. Where `pyboolector` has no wheel (Windows, Linux on
arm64), dv-solve is the default. See doc/source/solver_backends.rst.

On Boolector, a given seed produces the same values as 0.9.7, except where one
of the fixes below changes the result. Those changes are corrections: 0.9.7
either broke a constraint or ignored it. `pyvsc<1` keeps the 0.9.7 behavior
exactly. With the default settings, Boolector also keeps 0.9.7's draw order, so
the direct-draw tier (T0) is off by default on Boolector. `VSC_T0=1` turns it
on. That changes the values drawn for a seed and makes large unconstrained
arrays much faster.

### New
- dv-solve back-end (opt-in, see above). On dv-solve the direct-draw tier is on
  by default; `VSC_T0=0` turns it off.
- Dataclass front-end (`import vsc.dc as vdc`): constraint bodies follow a
  Python grammar. `and`/`or`/`not`, `if`/`elif`/`else`, `match`, `for` over
  arrays and constants, `x in {...}` / `range(...)` / named collections,
  `len`/`sum`/`math.prod`/`all`/`any`/`abs`/`min`/`max`, and class constants
  read per subclass. Anything else is rejected when the class is defined, with
  its file and line. See doc/source/dataclass/constraint_grammar.rst.
- vdc `randomize_with` bodies are parsed with the same grammar instead of run;
  values from the caller are read on every call. See
  doc/source/dataclass/inline_constraints.rst.
- dv-solve solves fields and constants up to 2^24 bits wide (was 65535).
- dv-solve's BV-SAT sampler (fields over 64 bits, and the shapes the primary
  engine cannot compile soundly) runs in the engine: a 65536-bit draw went from
  ~1.2 s to tens of ms, a 4096-bit one from 72 ms to 5 ms.

### Behavior changes
- vdc `randomize_with` bodies are parsed by default. A body written for the
  old operator path can behave differently (`/` is an error; `and`, `not`,
  `if` now mean what they say; a statement without `it` is an error).
  `VSC_DC_INLINE_PARSE=0` restores the old path. On that path (also used when
  a body's source cannot be read), `and`/`or`/`not`/`if` on a constraint
  expression now raise `TypeError` instead of dropping a constraint.
- Boolector: `~a` inverts after widening to the expression's width, as
  SystemVerilog and dv-solve do (`~a == 0xF0` with an 8-bit `a` never holds).
- dv-solve: an expression with a signed and an unsigned operand is unsigned
  (SystemVerilog); a signed operand is read as its bit pattern.
- vdc: a statement-level `and` or comparison chain is split into separate
  statements (same meaning; lets `1 < len(arr) < 4` bound a random-size array).
- dv-solve does not hand a set of constraints it cannot solve to Boolector:
  it raises `vsc.SolverUnsupported`, naming the reason. The only such set left
  is a random field wider than 2^24 bits. `VSC_DVSOLVE_FALLBACK=boolector`
  restores the fallback for 1.x (it is removed in 2.0), and
  `VSC_SOLVER=boolector` uses Boolector throughout. `VSC_DVSOLVE_BVSAT=0` and
  `VSC_DVSOLVE_BVSAT_SERVE_SAT=0`, which deferred to Boolector, are gone. See
  doc/source/solver_backends.rst.

### Fixes (classic and vdc)
- `arr[i]` with a random `i` used `i`'s value from before the solve (fresh
  objects put the value in `arr[0]`); a random bit-select `a[i]` likewise; an
  out-of-range pre-solve index raised `IndexError`.
- `x == r + k` (random `r`, non-random `k`) pinned `x` before the solve; on
  dv-solve `r` was always 0.
- Sum and product of a random-size array: built over the size's value before
  the solve, so `arr.sum == K` failed in ~20% of solves, or (with the size
  solved together with the elements) gave wrong sums silently.
- `x in arr` and `arr.sum` over a random-size array were wrong on both
  back-ends; classic `arr.sum == field` on a random-size array crashed.
- Boolector reused a destroyed instance's node for `arr.product` on the next
  randomize.
- A reused inline constraint block kept the previous solve's array expansion.
- A non-random array's size could be overwritten during a randomize call.
- `dist` with a range followed by a value inside it (`[10:13] :/ 1, 12 := 1`)
  cut the field's domain short, so 13 was never drawn on dv-solve.
- `objs[i].v`, `objs[i].sub.w` and `objs[i].arr[j]` with a random `i` used
  `i`'s value from before the solve, so the constraint held on that one element
  whatever `i` was solved to; `objs[2].arr[j]` with a random `j` raised
  `NotImplementedError`.

### Fixes (vdc)
- A constant-false constraint statement was dropped; `~` of a class constant
  was folded as logical not; a docstring in a constraint was an error; an array
  slice crashed at randomize.
- A loop name equal to a field name hid the field.
- `max_size=` on a scalar array was ignored.
- `randomize_with`: `it.arr[k]` failed.
- `self.arr[-1]` on a random-size array read the previous solve's last
  element.

## 0.9.7
Performance only. For a given seed, every randomized value is the same as in
0.9.6.
- Record source locations with `sys._getframe` instead of `inspect.stack()`. This
  applies when constructing randobj, covergroup and generator objects, and on
  every `randomize()` and `randomize_with` call. The cost no longer grows with
  call-stack depth: constructing an object 40 frames deep is about 7x faster, and
  `randomize()` is 1.2x faster at depth 0 and 2x at depth 100.
- `ValueScalar.__int__` returns a plain `int`. This also removes a Python
  `DeprecationWarning`.
- `list_t` defines its iterator classes once instead of on every `__iter__` call.
- Release packaging: the tag is the version, and the ungated Azure publisher is
  removed.

## 0.9.6
- (#282) - Enusre that dist weights respect randomized value of rand fields in expressions

## 0.9.5
- (#237) - Add support for specifying cross-bins to ignore

## 0.9.4
- (#233) - Propagate docstring and modulename across `randobj` inheritance

## 0.9.3
- () - Properly apply ignore bins to single-value bins

## 0.9.2
- (#224) - Ensure fields within expressions can be referenced

## 0.9.1
- (#221) - Correct a random-stability issue due to solve-order directives
- 
## 0.9.0
- (#219) - Add `unique_vec` constraint to support unique-vector constraints

## 0.8.9
- (#205) - Ensure that recursive references between objects don't cause recursion

## 0.8.8
- Ensure covergroup type names are properly reflected in saved coverage data.
- Test suite updates to adapt to newer Python versions
- Bump required version of PyUCIS to 0.1.3

## 0.8.7
- (#199) - Correct how the swizzler handles 'not inside'. It was incorrectly treating
           it the same as 'inside'

## 0.8.6
- (#191) - Fix from @alwilson to ensure proper priority of dist vs soft constraints
- (exp) - Add experimental covergroup callback
- 
## 0.8.5
- (#189) - Correct an issue with how arrays with constraints on sum are 
  grouped into rand sets. 

## 0.8.4
- (#188) - Automatically convert floating-point numbers used in constraints
  to integers

## 0.8.3
- (#176) [Resolved by Alex Wilson] Correctly handle soft constraints
  that are under conditions such as if/else. 

## 0.8.2
- (#172) Change list subscript to return a ValueInt such that the 
   value returned by a list subscript can, itself, be subscripted

## 0.8.1
- (#135) Add an 'original_module' field to randobj classes so true declaration
  location can be determined
  
## 0.8.0
- (#166) Correct rand-size list support for composite elements

## 0.7.9
- (#164) Correct issue with handling of soft constraints declared in dynamic-constraint blocks

## 0.7.8
- (#163) Remove an accidentally-committed debug message

## 0.7.7
- (#161) Adjust swizzling algorithm to improve multi-variable distribution

## 0.7.6
- (#160) Cache a coverpoint's target value to improve efficiency when 
  computing the target value is time consuming 

## 0.7.5
- Adjust PyUCIS dependencies to ensure presence of critical bug fix
- Test updates to adjust to change in PyUCIS report functionality

## 0.7.4
- Adjust to deprecated PyUCIS functionality

## 0.7.3
- Correct an issue with the covergroup 'get_coverage' method

## 0.7.2
- Disable some internal debug output that was inadvertently left on

## 0.7.1
- (#156) Correct random distribution for signed variables constrained to negaitve value ranges

## 0.7.0
- (#146) Correct an issue with enums and the new constant-expression eval from #132

## 0.6.9
- (#132) Evaluate constant 'if' conditions in foreach

- (#145) Correct 'unique' constraint to handle single-element lists

## 0.6.8
- (#127) Change randomization scheme to make better use of domain info

## 0.6.7
- (#143) Correct a failure when no source information is available

## 0.6.6
- #(142) Resolve random instability due to use of 'dist' constraints

## 0.6.5
- (#133) Use built-in Random package in RandState [Michael McGrath]

## 0.6.4
- (#128) Add support for modifying the defintion of rangelists

## 0.6.3
- (#117) Add support for explicitly managing random stability

## 0.6.2
- (#119) Correct accidental import of attr.exclude

## 0.6.1
- (#111) Add support for illegal and ignore bins

## 0.6.0
- (#115) Correct an issue with Jupyter notebooks and inability
  to obtain source information
- (#59) Add environment-variable support for controlling 
  enhanced diagnostic messages, and add documentation

## 0.5.9
- (#107) Added a new randomization approach that deals better
  with bit conflicts.

## 0.5.8
- (#110) Correct an issue with variable-bound calculation
  in the presence of part selects.

## 0.5.7
- (#108) Correct an issue with specifying individual kwarg
  sample arguments to with_sample instead of passing a dict()

- (#nobug) Correct an issue with an auto-binned single-bit
  variable that resulted in a single bin instead of two
  array bins

## 0.5.6
- (#nobug) Fix for random instability

## 0.5.5
- (#nobug) Work on removing undesirable sources of randomness
  due to use of sets/maps. 

- (#nobug) Make source-information collection and solve-failure
  diagnosis on-request, due to performance overhead

## 0.5.4
- (#nobug) Correct an issue with expanding wildcard bins.
  Regions were incorrectly being merged.

## 0.5.3
- (#105) Correct an issue when collapsing overlapping bins
  in a wildcard bin array

## 0.5.2
- (#77) Add support for wildcard bins. Both single and
  array bins are supported.

## 0.5.1
- Adjust the debug approach to collect singles, pairs,
  triples of failing constraints.
- Add the very beginnings of a linting feature

## 0.5.0
- (#90) Correct issues with use of dynamic constraint defined
  within an array of composite types

## 0.4.9
- (#97) Correct issues with support of part select as a general expression

## 0.4.8
- (#95) Correct issues with multi-level nested foreach constraints

## 0.4.7
- Added the beginnings of a rudimentary solve profiler
  to collect statistics on class randomization. It's
  currently undocumented, but enabled with the environment
  variable VSC_PROFILE=1
## 0.4.6
- (#89) Correct general solution-bias issue when using 
  dynamic constraints
  
## 0.4.5
- (#93) Support slices/part selects on int/bit-type fields in
  procedural code. 
- (#83) Correct an issue with variable-bounds detetion that
  resulted in little randomization being applied to 
  constrained nested fields
## 0.4.4
- (#92) Corrected an issue where soft constraints were dropped while
  combining solve sets
- (#91) Corrected the field-access overloading to properly handle
  re-assignment to VSC fields
- (#88) Correct how the width of unary expressions is propagated 
- (#87) Correct handling of enum-type fields by increasing common
  implementation with scalar/int-type fields
- (#86) Properly handle part-select on array-element references
- (#85) Correct an issue with complex-reference resolution and
  dist constraints
- (#84) Correct an issue with expanding complex references inside
  foreach constraints

## 0.4.3
- (#81,#82) Correctly propagate context-dependent expression widths 
  down the evaluation tree

## 0.4.2
- Correct the build process for Boolector nodes to only build
  needed nodes for arrays. This avoids nodes being left behind.

## 0.4.1
- Correct an issue with constraints on nested arrays of objects
- Correct an issue where disabling a constraint in one 
  compound-array 'branch' resulted in disabling the constraint
  in a different branch

## 0.4.0
- Correct an issue with using literal array indexes on arrays of
  classes (eg self.arr[0].field < 10). 

## 0.3.9
- Adjust the randomization process to produce better spread of results.
  Previously, a single field was selected from each randset. Now, a 
  random ordering of up to N (4) fields is selected.

## 0.3.8
- Adjust the solve-ordering algorithm to affect randomization
  order and priority instead of solve-set partitioning

## 0.3.7
- Add priorities to soft constraints
- Change randomization strategy to select a single value
- Make randomization aware of dist constraints
- Give dist soft constraints a high (1M+) priority to distiguish from 
  user soft constraints

## 0.3.6
- Add support for passing VSC class objects to the covergroup sample method

## 0.3.5
- (#70) - Correct bugs and improve test suite for handling of signed types. 

- (#71) - Correct handling of 'at_least' option for coverpoints and crosses

## 0.3.4
- (#69) - Properly deal with two's complement conversion to Python signed number

## 0.3.3
- (#68) - Update width of array-sum result to avoid overflow

## 0.3.2
- (#60) - Correct issues handling 'iff' on coverpoints and crosses

## 0.3.1
- (#61) - Correct an issue with multiple failing soft constraints

## 0.3.0
- (#57) - Correct an issue with cross coverage on enum-type bins

## 0.2.9
- Correct an issue with array-bin specifications involving individual values.
- Added 'get_coverage' to cross
- Ensured that bin collections are properly recorded for crosses

## 0.2.8
- Correct an issue with random-sized arrays being 'pinned' to a single size

## 0.2.7
- (#45) - Correct an issue with approximate array sizing due to varaible-bound limitations
- Improve bounding of variables for randomization
  - Add propagators for equality relationships (a == b)
  - Add propagators for variable inequalities (a < b) to match constant inequalities


## 0.2.6
- (#44) - Correct an issue with nested if_then and foreach constructs
- (nobug) - Correct an issue with auto-conversion from scalar to bool

## 0.2.5
- (#43) - Correct an issue with enum-type fields and solve-fail diagnostics
- (#34) - Correct an issue with arrays and solve-order constraints

## 0.2.4
- (#42) Add support for randcase-like functionality, with a randselect method
- (#34) Add support for solve ordering with a solve_order statement

## 0.2.3
- (#41) Correct an issue with the slice operator used in procedural code

## 0.2.2
- Correct handling of if/else-if constraints in foreach blocks

## 0.2.1
- Ensure all variables referenced by inline constraints are considered

## 0.2.0
- Add basic solve-failure diagnostics

## 0.1.9
- Correct an issue with using inline foreach constraints

## 0.1.8
- (#36) Correct issues with random distribution
- (#19) Implement sum and product constraints on arrays

## 0.1.7
- (#36) Support using vsc.range in weights

## 0.1.6
- (#26) Correct issues with dist constraints on array elements.
- (#26) Improve distribution algorithm

## 0.1.5
- Correct issues with nested foreach constraints
- (#31) Correct issues with not_inside on a rand-size list
- (#26) Provide support for 'dist' constraints
- (#30) Correct issues with masking assignments to sized fields, and accessing enum-type fields


## 0.1.4
- Correct issues with nested foreach constraints and nested arrays
- Add global 'write_coverage_db' method

## 0.1.3
- (#31) Allow 'inside' constraint on array elements within a foreach constraint

## 0.1.2
- (#27) Correct several issues with coverpoint cross coverage and
  reporting. 

## 0.1.1
- (#30) Add support for part-select operator on standalone fields, 
        and on fields used in 'raw_mode'
- Correct some issues with enumerated-type introspection and
  coverage sampling        

## 0.1.0
- (#24) Correct an issue with sampling of type-centric coverage

## 0.0.9
- Correct issues with using scalar variables standalone
- Add global randomize() and randomize_with() methods for 
  use with standalone variables

## 0.0.8
- Correct several issues (and add tests) for coverpoints defined on enumerated types

## 0.0.7
- Add support for 'rand_mode' on scalar fields
- (#17) Correct an issue with reported size of a list after appending to it

## 0.0.6
- Adds support for rand and non-rand lists of enum
- Ensures unique constraint works on lists

## 0.0.5
- Adds support for 'inside' and 'not_inside' methods
  on scalar data types, to address limitations in the ability
  to overload Python's 'in' operator.

## 0.0.4
- Adds support for randomizable lists
- Adds foreach constraint



