
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



