#################
PyVSC Constraints
#################

Constraint Blocks
=================

Constraint blocks are class methods decorated with the `constraint`
decorator. Dynamic constraint blocks are decorated with the 
`dynamic_constraint` decorator.

Constraint blocks are 'virtual', in that constraints can be overridden
by inheritance. 

.. code-block:: python3

     @vsc.randobj
     class my_base_s(object):
         
         def __init__(self):
             self.a = vsc.rand_bit_t(8)
             self.b = vsc.rand_bit_t(8)
             self.c = vsc.rand_bit_t(8)
             self.d = vsc.rand_bit_t(8)
             
         @vsc.constraint
         def ab_c(self):
            self.a < self.b
            
     @vsc.randobj
     class my_ext_s(my_base_s):
         
         def __init__(self):
             super().__init__()
             self.a = vsc.rand_bit_t(8)
             self.b = vsc.rand_bit_t(8)
             self.c = vsc.rand_bit_t(8)
             self.d = vsc.rand_bit_t(8)
             
         @vsc.constraint
         def ab_c(self):
            self.a > self.b

Instances of ``my_base_s`` will ensure that ``a`` is less than ``b``. Instances
of ``my_ext_s`` will ensure that ``a`` is greater than ``b``.


Expressions
===========

Dynamic-constraint Reference
----------------------------
Constraint blocks decorated with `constraint` always apply. 
Dynamic-constraint blocks, decorated with `dynamic_constraint` only
apply when referenced. A dynamic constraint is referenced using syntax
similar to a method call.

Dynamic constraints provide an abstraction mechanism for applying a
condition without knowing the details of what that condition FIXME.

.. code-block:: python3

        @vsc.randobj
        class my_cls(object):
            
            def __init__(self):
                self.a = vsc.rand_uint8_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def a_c(self):
                self.a <= 100
                
            @vsc.dynamic_constraint
            def a_small(self):
                self.a in vsc.rangelist([1,10])
                
            @vsc.dynamic_constraint
            def a_large(self):
                self.a in vsc.rangelist([90,100])
                
        my_i = my_cls()

        with my_i.randomize()

        with my_i.randomize_with() as it:
            it.a_small()
        
        with my_i.randomize_with() as it:
            it.a_large()
            
        with my_i.randomize_with() as it:
            it.a_small() | it.a_large()

The example above defines two dynamic constraints. One ensures that the
range of ``a`` is inside 1..10, while the other ensures that the range of
``a`` is inside 90..100.

The first randomization call results in a value of a across the full
value of ``a`` (0..100).

The second randomization call results in the value of ``a`` being 1..10. 

The third randomization call results in the value of ``a`` being 90..100.

The final randomization call results in the value of ``a`` being either
1..10 or 90..100.

in
--
The ``in`` constraint ensures that the value of the specified variable 
stays inside the specified ranges. Both individual values and 
ranges may be specified. In the example below, the value of ``a`` will be
1, 2, or 4..8. The value of ``b`` will be between ``c`` and ``d`` (inclusive).

.. code-block:: python3

     @vsc.randobj
     class my_s(object):
         
         def __init__(self):
             self.a = vsc.rand_bit_t(8)
             self.b = vsc.rand_bit_t(8)
             self.c = vsc.rand_bit_t(8)
             self.d = vsc.rand_bit_t(8)
             
         @vsc.constraint
         def ab_c(self):
             
            self.a in vsc.rangelist(1, 2, [4,8])
            self.c != 0
            self.d != 0
                
            self.c < self.d
            self.b in vsc.rangelist([self.c,self.d])

part select
-----------

.. code-block:: python3

     @vsc.randobj
     class my_s(object):
         
         def __init__(self):
             self.a = vsc.rand_bit_t(32)
             self.b = vsc.rand_bit_t(32)
             self.c = vsc.rand_bit_t(32)
             self.d = vsc.rand_bit_t(32)
             
         @vsc.constraint
         def ab_c(self):
             
             self.a[7:3] != 0
             self.a[4] != 0
             self.b != 0
             self.c != 0
             self.d != 0

Statements
==========

if/else
-------
if/else constraints are modeled using three statements:

- `if_then`   -- simple if block
- `else_if`   -- else if clause
- `else_then` -- terminating else clause

.. code-block:: python3

     @vsc.randobj
     class my_s(object):
         
         def __init__(self):
             self.a = vsc.rand_bit_t(8)
             self.b = vsc.rand_bit_t(8)
             self.c = vsc.rand_bit_t(8)
             self.d = vsc.rand_bit_t(8)
             
         @vsc.constraint
         def ab_c(self):
             
             self.a == 5
             
             with vsc.if_then(self.a == 1):
                 self.b == 1
             with vsc.else_if(self.a == 2):
                 self.b == 2
             with vsc.else_if(self.a == 3):
                 self.b == 4
             with vsc.else_if(self.a == 4):
                 self.b == 8
             with vsc.else_if(self.a == 5):
                 self.b == 16

implies
-------

.. code-block:: python3

     @vsc.randobj
     class my_s(object):
         
         def __init__(self):
             super().__init__()
             self.a = vsc.rand_bit_t(8)
             self.b = vsc.rand_bit_t(8)
             self.c = vsc.rand_bit_t(8)
             self.d = vsc.rand_bit_t(8)
             
         @vsc.constraint
         def ab_c(self):
             
             self.a == 5
             
             with vsc.implies(self.a == 1):
                 self.b == 1
                  
             with vsc.implies(self.a == 2):
                 self.b == 2
                  
             with vsc.implies(self.a == 3):
                 self.b == 4
                  
             with vsc.implies(self.a == 4):
                 self.b == 8
                  
             with vsc.implies(self.a == 5):
                 self.b == 16

unique
------
The `unique` constraint ensures that all variables in the specified list have
a unique value. 

.. code-block:: python3

     @vsc.rand_obj
     class my_s(object):
         
         def __init__(self):
             self.a = vsc.rand_bit_t(32)
             self.b = vsc.rand_bit_t(32)
             self.c = vsc.rand_bit_t(32)
             self.d = vsc.rand_bit_t(32)
             
         @vsc.constraint
         def ab_c(self):
             self.a != 0
             self.b != 0
             self.c != 0
             self.d != 0
             
             vsc.unique(self.a, self.b, self.c, self.d)

