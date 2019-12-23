
- Support common covergroup styles
  - Embed in class with reference to containing scope
  - Declare as a reusable type ; Bind to context variables at instantiation
    - Must explicitly specify coverpoint type
  - Declare with a sampling function ; Pass values in at sample
    - Parameter types are specified up-front

- Do not care about clocked sampling
- Do not care about coverpoint-less crosses

- Support instance-based coverage
- Support type-based coverage
- Support covergroup options
  - At declaration
  - At instantiation
  - Configuration any time before first sample since several
    parameters affect bin organization
    
- Need a central registry for covergroup models
- 


- Sample function that accepts parameters
- Ability to specify the signature of the sample function as a type property
  - Strictly speaking, could do so within the constructor as well
  
- 