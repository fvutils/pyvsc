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
condition without knowing the details of what that condition is.

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
                self.a in vsc.rangelist(vsc.rng(1,10))
                
            @vsc.dynamic_constraint
            def a_large(self):
                self.a in vsc.rangelist(vsc.rng(90,100))
                
        my_i = my_cls()

        my_i.randomize()

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
PyVSC provides two ways of expressing set-membership constraints. Python's
``in`` operator may be used directly to express simple cases. More complex
cases, including negation of set-membership, may be captured using the
`inside` and `not_inside` methods on PyVSC scalar data types.

The ``in`` constraint ensures that the value of the specified variable 
stays inside the specified ranges. Both individual values and 
ranges may be specified. In the example below, the value of ``a`` will be
1, 2, or 4..8. The value of ``b`` will be between ``c`` and ``d`` (inclusive).

The right-hand side of an 'in' constraint must be a ``rangelist`` expression.
Elements in a ``rangelist`` may be:
- individual expressions
- ranges of expressions, using ``rng`` or a tuple of two expressions
- a list of expressions or ranges

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
             
            self.a in vsc.rangelist(1, 2, vsc.rng(4,8))
            self.c != 0
            self.d != 0
                
            self.c < self.d
            self.b in vsc.rangelist(vsc.rng(self.c,self.d))
           
PyVSC scalar data types provide `inside` and `not_inside` methods that to express
set membership.

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
             
            self.a in vsc.rangelist(1, 2, vsc.rng(4,8))
            self.c != 0
            self.d != 0
                
            self.c < self.d
            self.b.inside(vsc.rangelist(1, 2, 4, 8))
            self.c.not_inside(vsc.rangelist(1, 2, 4, 8))

In the example above, the `b` variable will be inside the range (1,2,4,8). 
The `c` variable will be outside (ie not equal to) (1,2,4,8)

Mutable Rangelists
------------------

It is sometimes useful to change the value/range list used in an 
`in` constraint between randomizations. The `rangelist` class can be
constructed as a class member, referenced in constraints, and modified
between calls to `randomize`. 

The `rangelist` class provides three methods to modify the values in 
a rangelist after it has been created:

- append() -- Add a new value or range tuple
- clear() -- Remove all previously-added ranges
- extend() -- Add a list of values and/or range tuples to the rangelist


.. code-block:: python3

        @vsc.randobj
        class Selector():
            def __init__(self):
                self.availableList = vsc.rangelist((0,900))
                self.selectedList = vsc.rand_list_t(vsc.uint32_t(), 15)
        
            @vsc.constraint
            def available_c(self):
                with vsc.foreach(self.selectedList) as sel:
                    sel.inside(self.availableList)
        
            def getSelected(self):
                '''Returns a sorted list of selected integers.'''
                selected = []
                for resource in self.selectedList:
                    selected.append(int(resource))
                selected.sort()
                return selected
                
        selector = Selector()
        
        selector.randomize()
        
        selector.availableList.clear()
        selector.availableList.extend([(1000, 2000)])
        
        selector.randomize()
        
        
In the example above, the rangelist is initially created to contain
a value range of 0..900. All values in the `selectedList` produced
by the first randomization will fall in this range. 

The rangelist is subsequently cleared, and a new range 1000..2000
added. The second randomization will produce values in the 1000..2000 
range.

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

dist
----
Distribution constraints associate weights with values or value ranges
of the specified variable.

.. code-block:: python3

    @vsc.randobj
    class my_c(object):
            
        def __init__(self):
            self.a = vsc.rand_uint8_t()
                
        @vsc.constraint
        def dist_a(self):
            vsc.dist(self.a, [
                vsc.weight(1, 10),
                vsc.weight(2, 20),
                vsc.weight(4, 40),
                vsc.weight(8, 80)])

Any otherwise-legal values for the variable that does not have a non-zero 
weight associated will be excluded from the legal value set. The example
above associates non-zero weights with 1, 2, 4, 8. So, a value such as '3'
will not be produced.

.. code-block:: python3

    @vsc.randobj
    class my_c(object):
            
        def __init__(self):
            self.a = vsc.rand_uint8_t()
                
        @vsc.constraint
        def dist_a(self):
            vsc.dist(self.a, [
                vsc.weight((10,15),  80),
                vsc.weight((20,30),  40),
                vsc.weight((40,70),  20),
                vsc.weight((80,100), 10)])

Ranges for weights are specified as a tuple, as shown above.


foreach
-------
foreach constraints are modeled with the `foreach` class. By default, 
the foreach iterator is a reference to the current element of the array.

.. code-block:: python3

     @vsc.randobj
     class my_s(object):
         def __init__(self);
             self.my_l = vsc.rand_list_t(vsc.uint8_t(), 4)
             
         @vsc.constraint
         def my_l_c(self):
             with vsc.foreach(self.my_l) as it:
                 it < 10
                 
The `foreach` class supports control over whether the item, index,
or both is provided for use in constraints.

Here is an example of requesting the index instead of the iterator.

.. code-block:: python3

     @vsc.randobj
     class my_s(object):
         def __init__(self);
             self.my_l = vsc.rand_list_t(vsc.uint8_t(), 4)
             
         @vsc.constraint
         def my_l_c(self):
             with vsc.foreach(self.my_l, idx=True) as i:
                 self.my_l[i] < 10
                 
Here is an example of explicitly requesting the iterator.

.. code-block:: python3

     @vsc.randobj
     class my_s(object):
         def __init__(self);
             self.my_l = vsc.rand_list_t(vsc.uint8_t(), 4)
             
         @vsc.constraint
         def my_l_c(self):
             with vsc.foreach(self.my_l, it=True) as it:
                 it < 10

Now, finally, here is an example of having both an iterator and
index.

.. code-block:: python3

     @vsc.randobj
     class my_s(object):
         def __init__(self);
             self.my_l = vsc.rand_list_t(vsc.uint8_t(), 4)
             
         @vsc.constraint
         def my_l_c(self):
             with vsc.foreach(self.my_l, it=True, idx=True) as (i,it):
                 it == (i+1)
                 

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
                 
soft
----
Soft constraints are enforced, except in cases where they violate
a hard constraint. Soft constraints are often used to set default 
values and relationships, which are then overridden by another
constraint. 

.. code-block:: python3

     @vsc.randobj
     class my_item(object):
         
         def __init__(self):
             self.a = vsc.rand_bit_t(8)
             self.b = vsc.rand_bit_t(8)
             
         @vsc.constraint
         def ab_c(self):
            self.a < self.b
            vsc.soft(self.a == 5)
            
    item = my_item()
    item.randomize() # a==5
    with item.randomize_with() as it:
      it.a == 6
    

The `soft` constraint applies to a single expression, as shown above. 
Soft constraints are disabled if they conflict with another hard
constraint declared in the class or introduced as an inline constraint.

solve_order
-----------
Solve-order constraints are used to provide the user control over
value distributions by ordering solve operations. The PyVSC `solve_order`
statement corresponds to the SystemVerilog `solve a before b` statement.

.. code-block:: python3

        @vsc.randobj
        class my_c(object):
            
            def __init__(self):
                self.a = vsc.rand_bit_t()
                self.b = vsc.rand_uint8_t()
                
            @vsc.constraint
            def ab_c(self):
                vsc.solve_order(self.a, self.b)

                with vsc.if_then(self.a == 0):
                    self.b == 4
                with vsc.else_then:
                    self.b != 4

In the example above, te `solve_order` statement causes `b` to
have values evenly distributed between the value sets [4] and 
[0..3,5..255].

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

Customizing Constraint Behavior
===============================

In general, the bulk of constraints should be declared inside a class and 
should always be enabled. However, there are often cases where these base
constraints need to be customized slightly when the class is used in 
a test. PyVSC provides several mechanisms for customizing constraints.

Randomize-With
--------------

Classes decorated with the `randobj` decorator are randomized by calling
the `randomize` method, as shown in the example below.

.. code-block:: python3

     @vsc.randobj
     class my_base_s(object):
         
         def __init__(self):
             self.a = vsc.rand_bit_t(8)
             self.b = vsc.rand_bit_t(8)
             
         @vsc.constraint
         def ab_c(self):
            self.a < self.b

    item = my_base_s()
    item.randomize()

PyVSC also provides a `randomize_with` method that allows additional 
constraints to be added in-line. The example below shows using this
to constraint `a` to explicit values.

.. code-block:: python3

     @vsc.randobj
     class my_base_s(object):
         
         def __init__(self):
             self.a = vsc.rand_bit_t(8)
             self.b = vsc.rand_bit_t(8)
             
         @vsc.constraint
         def ab_c(self):
            self.a < self.b

    item = my_base_s()
    for i in range(10):
       with item.randomize_with() as it:
         it.a == i


    
Constraint Mode
---------------

All constraints decorated with the `constraint` decorator can be enabled
and disabled using the `constraint_mode` method. This allows constraints
to be temporarily turned off. For example, a constraint that enforces
valid ranges for certain variables might be disabled to allow testing
design response to illegal values.


.. code-block:: python3

     @vsc.randobj
     class my_item(object):
         
         def __init__(self):
             self.a = vsc.rand_bit_t(8)
             self.b = vsc.rand_bit_t(8)
             
         @vsc.constraint
         def valid_ab_c(self):
            self.a < self.b

    item = my_item()
    # Always generate valid values
    for i in range(10):
       with item.randomize():
       
    item.valid_ab_c.constraint_mode(False)

    # Allow invalid values
    for i in range(10):
       with item.randomize():
   
Rand Mode
---------
The random mode of rand-qualified fields can be changed using the `rand_mode`
method. This allows randomization of rand-qualified fields to be programmatically
disabled.

Due to the operator overloading that PyVSC uses to enable direct access to 
the value of class attributes, a special mode must be entered in order to
access or modify rand_mode.

.. code-block:: python3

     @vsc.randobj
     class my_item(object):
         
         def __init__(self):
             self.a = vsc.rand_bit_t(8)
             self.b = vsc.rand_bit_t(8)
             
         @vsc.constraint
         def valid_ab_c(self):
            self.a < self.b

    item = my_item()
    # Randomize both 'a' and 'b'
    for i in range(10):
       with item.randomize():
       
    # Disable randomization of 'a'
    with vsc.raw_mode():
        item.a.rand_mode = False
        
    # Randomize only 'b'
    for i in range(10):
       with item.randomize():
       


