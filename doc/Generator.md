
- A generator is a random object that contains a covergroup
  linked to the fields in the random object. 
  
- Stimulus is generated with additional constraints to focus
  on un-hit coverage. 

- Generator holds a map of coverage goals to stimulus-class expressions
  - CP n-bins, expr mapping bin index to conditions
  
bins[] = {1, 2, 4, 8}

# Better/worse than using a temp var?
ite((e==1), 0, 
  ite((e==2), 1,
    ite((e==4), 2,
      ite((e==8), 3, -1)
      )
    )
  )
)

# Need to cover 0, 1, 2, 3 (0..nbins-1)

# Cross: list of bin indices

# Should 

