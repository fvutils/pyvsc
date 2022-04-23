
PyVSC2 uses dataclasses to represent random classes. This allows the 
characteristics of class 'types' to be captured once. It also adds some
degree of complication to the decorator and object-creation process. 
However, the performance and capability improvements should be well
worth it.

# Type Capture Phase
Type capture occurs when the `randclass` decorator is evaluated during
module loading. The decorator does the following:
  - Invokes the dataclass decoarator to populate field info
  - Constructs a native object (eg IDataTypeStruct) to represent the type
  - Processes constraints registered with @constraint. Each class only
    sees the constraints registered with itself, so base types are 
    manually processed to arrive at the full set of constraints.
  - Process dataclass fields. Unlike 'real' dataclass fields, PyVSC users
    do not specify how the field is implemented. PyVSC must create 
    field-type information for each field, as well as back-patch
    implementations for rand and non-rand fields.
    - Each recognized field type 

