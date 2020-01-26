
- Data Types
  - Enumerated types
    - Use cases
      - Comparison against same type (f.a != MODE_A)
      - Using as an integral quantity (f.a in range([COEFF_A:COEFF_B]))
  - Arrays
    - Fixed-sized
    - Variable-sized
  - Bool type
  - inline range specification on variables
  - randc

- Constraints and Expressions
  - Part select (a[3:0], a[1])
  - Constraint enable/disable
  - soft constraints
    
- Public API
  - std::randomize() and std::randomize() with equivalents
    - operate on 'vsc' variables
    - build inline constraints on-the-fly
  - Checking (randomize(None))
  
- Model
  - Programmatic construction mixed with eDSL construction
  
  
- Coverage
  - Bins
    - Transition
    - ignore_bins, illegal_bins
  - Type coverage
  - Covergroup options
  - Coverpoint options
  - Cross exclusion bins
  
