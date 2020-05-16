############
Introduction
############

What is PyVSC?
==============
PyVSC is a Python library that implements random verification-stimulus
generation and coverage collection. PyVSC provides this capability 
in two forms: an object-oriented Model API, and a Python-embedded 
domain-specific language built on top of the Model API. This allows
coverage and randomization features to be programmatically built, 
defined with user-friendly constructs, or defined using a mix of the two.

One great way to get an overview of PyVSC is to read a series of
blog posts about PyVSC. Links are below:

- `The fundamentals of modeling stimulus and functional coverage in Python <http://bitsbytesgates.blogspot.com/2020/03/modeling-random-stimulus-and-functional.html>`_.
- `Modeling verification data types in Python <http://bitsbytesgates.blogspot.com/2020/04/python-verification-stimulus-and.html>`_.
- `Modeling and capturing functional coverage in Python <http://bitsbytesgates.blogspot.com/2020/04/python-verification-and-stimulus.html>`_.
- `Making use of captured coverage data <http://bitsbytesgates.blogspot.com/2020/04/python-verification-working-with.html>`_.



Currently, the Python-embedded domain-specific language supports 
similar features to those supported by SystemVerilog. Not all SystemVerilog
features are supported, but in some cases features not supported by
SystemVerilog are also supported. Please see the following section 
:ref:`pyvsc-features` for a comparison of the user-level coverage 
and randomization features supported by PyVSC compared to SystemVerilog.

Here is a quick example showing capturing random data fields, constraints,
coverage, and inline randomization.

.. code-block:: python3

    @vsc.randobj
    class my_item_c(object):
        def __init__(self):
            self.a = vsc.rand_bit_t(8)
            self.b = vsc.rand_bit_t(8)

         @vsc.constraint
         def ab_c(self):
             self.a != 0
             self.a <= self.b
             self.b in vsc.rangelist(1,2,4,8)

      @vsc.covergroup
      class my_cg(object):

          def __init__(self):
              # Define the parameters accepted by the sample function
              self.with_sample(dict(
                  it=my_item_c()
               ))

               self.a_cp = vsc.coverpoint( self.it.a, bins=dict(
                  # Create 4 bins across the space 0..255
                  a_bins = bin_array([4], [0,255])
               )
               self.b_cp = vsc.coverpoint(self.it.b, bins=dict(
                  # Create one bin for each value (1,2,4,8)
                  b_bins = bin_array([], 1, 2, 4, 8)
               )
               self.ab_cross = vsc.cross([self.a_cp, self.b_cp])

      # Create an instance of the covergroup
      my_cg_i = my_cg()

      # Create an instance of the item class
      my_item_i = my_item_c()

      # Randomize and sample coverage
      for i in range(16):
          my_item_i.randomize()
          my_cg_i.sample(my_item_i)

      # Now, randomize keeping b in the range [1,2]
      for i in range(16):
          with my_item_i.randomize_with() as it:
              it.b in vsc.rangelist(1,2)
          my_cg_i.sample(my_item_i)

      print("Coverage: %f \%" % (my_cg_i.get_coverage()))


        




Contributors
============

.. spelling::
   Ballance

