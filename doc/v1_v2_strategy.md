

- V2 brings in dataclasses and a type-based approach to class specification
--> V2 retains randobj-style class, but changes implementation a bit
--> randobj-style class is the less-preferred option due to performance/debug considerations

- V2 builds on libvsc vs directly on pyboolector
--> Can be instability due to libvsc
--> Should provide better performance / scalability

- V2 brings in a new nested-type style of field specifier
--> vsc.rand[vsc.bit_t[8]]
--> Must retain old type-specifier names

- V2 expects dataclasses to be fixed-definition
--> Single constraint specification
--> Single set of fields
--> Performs type-buildout on the Python side just once

- Can we implement templates with subscripted metaclasses?
-> Should result in seeing types as distinct

- V2 still provides randobj classes as a less-preferred option
--> New implementation to avoid actual derivation in implementation



