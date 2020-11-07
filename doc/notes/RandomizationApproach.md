
Steps
=====

- Organize variables into solve groups based on constraint relationships
- Create a bounds model for each related variable
  - Use domain information as a starting point
  - Handle inequalities involving a variable and a solve-constant expression
  - Handle in expressions
  - Handle equalities in post
  
- Dealing with equality
  - <field> == <const>
    - Fixes field to a single value. Means we should exclude field from randomization
  - <field> == <field>
     - Alias. Bounds are the intersect: maximum min and minimum max
 
- Randomly select a single variable in each solve group to 'swizzle' based on the bound
- Randomly select a range from the domain
    - If the domain of the range is > LIMIT (64)
        - Select a target value within the range
        - Select a style of randomization
            - Place a range within the target range centered around the target value
            - Place a range within the target range starting at the target value
            - Place a range within the target range ending at the target value
            - Select the target value
    - Else, target the entire range
    

  