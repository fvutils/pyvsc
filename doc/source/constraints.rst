==================
Py-VSC Constraints
==================


Expressions
-----------

- in

.. code-block:: python3

     class my_s(vsc.rand_obj):
         
         def __init__(self):
             self.a = vsc.rand_bit_t(8)
             self.b = vsc.rand_bit_t(8)
             self.c = vsc.rand_bit_t(8)
             self.d = vsc.rand_bit_t(8)
             
         @vsc.constraint
         def ab_c(self):
             
            self.a in vsc.rangelist(1, 2, 4, 8)
               

            self.c != 0
            self.d != 0
                
            self.c < self.d
            self.b in vsc.rangelist([self.c,self.d])

- part select

.. code-block:: python3
     class my_s():
         
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

- unique


Statements
----------

- if/else

.. code-block:: python3

     class my_s(vsc.RandObj):
         
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

- implies

.. code-block:: python3
     class my_s(vsc.Base):
         
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

- unqiue

.. code-block:: python3

     @vsc.rand_obj
     class my_s():
         
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

