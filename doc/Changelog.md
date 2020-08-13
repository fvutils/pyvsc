
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



