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



