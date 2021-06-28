'''
Created on Jun 26, 2021

@author: mballance
'''
from vsc_test_case import VscTestCase

class TestConstraintForeach(VscTestCase):
    
    def test_compound_array(self):
        import vsc 
        import random
        random.seed(0)

        @vsc.randobj
        class Parent:
            def __init__(self):
                self.id = 0
                self.c1 = vsc.rand_list_t(vsc.attr(Child1()))
                for i in range(10):    
                    self.c1.append(vsc.attr(Child1()))

                self.c2 = vsc.rand_list_t(vsc.attr(Child2()))
                for i in range(10):
                    self.c2.append(vsc.attr(Child2()))

            @vsc.constraint
            def parent_c(self):
                with vsc.foreach(self.c1, idx=True) as i:
                    self.c1[i].a[0].value == self.c2[i].x[0].value

        @vsc.randobj
        class Field():
            def __init__(self, name, def_value):
                self.name = name
                self.value = vsc.rand_uint8_t(def_value)

        @vsc.randobj
        class Child1:
            def __init__(self):
                self.a = vsc.rand_list_t(vsc.attr(Field('a', 10)))
                for i in range(5):    
                    self.a.append(vsc.attr(Field('a', 10)))

                self.b = vsc.rand_list_t(vsc.attr(Field('b', 10)))
                for i in range(5):    
                    self.b.append(vsc.attr(Field('b', 10)))
    
            @vsc.constraint
            def test_c(self):
                self.a[0].value < self.a[1].value

        @vsc.randobj
        class Child2:
            def __init__(self):
                self.x = vsc.rand_list_t(vsc.attr(Field('x', 10)))
                for i in range(5):    
                    self.x.append(vsc.attr(Field('x', 10)))

                self.y = vsc.rand_list_t(vsc.attr(Field('y', 10)))
                for i in range(5):    
                    self.y.append(vsc.attr(Field('y', 10)))
    
            @vsc.constraint
            def test_c(self):
                self.x[0].value < self.x[1].value

        inst=Parent()
        inst.randomize(debug=1)
        print(inst.c1[0].a[0].value)
        print(inst.c2[0].x[0].value)
        self.assertEqual(inst.c1[0].a[0].value, inst.c2[0].x[0].value)
        
    def test_compound_array_min(self):
        import vsc 
        import random
        random.seed(0)

        @vsc.randobj
        class Parent:
            def __init__(self):
                self.id = 0
                self.c1 = vsc.rand_list_t(vsc.attr(Child1()))
                for i in range(2):
                    self.c1.append(vsc.attr(Child1()))

                self.c2 = vsc.rand_list_t(vsc.attr(Child2()))
                for i in range(2):
                    self.c2.append(vsc.attr(Child2()))

            @vsc.constraint
            def parent_c(self):
                with vsc.foreach(self.c1, idx=True) as i:
                    self.c1[i].a[0].value == self.c2[i].x[0].value

        @vsc.randobj
        class Field():
            def __init__(self, name, def_value):
                self.name = name
                self.value = vsc.rand_uint8_t(def_value)

        @vsc.randobj
        class Child1:
            def __init__(self):
                self.a = vsc.rand_list_t(vsc.attr(Field('a', 10)))
                for i in range(2):
                    self.a.append(vsc.attr(Field('a', 10)))

                self.b = vsc.rand_list_t(vsc.attr(Field('b', 10)))
                for i in range(2):
                    self.b.append(vsc.attr(Field('b', 10)))
    
            @vsc.constraint
            def test_c(self):
#                self.a[0].value < self.a[1].value
                pass

        @vsc.randobj
        class Child2:
            def __init__(self):
                self.x = vsc.rand_list_t(vsc.attr(Field('x', 10)))
                for i in range(2):    
                    self.x.append(vsc.attr(Field('x', 10)))

                self.y = vsc.rand_list_t(vsc.attr(Field('y', 10)))
                for i in range(2):    
                    self.y.append(vsc.attr(Field('y', 10)))
    
            @vsc.constraint
            def test_c(self):
#                self.x[0].value < self.x[1].value
                pass

        inst=Parent()
        inst.randomize(debug=1)
        print(inst.c1[0].a[0].value)
        print(inst.c2[0].x[0].value)
        self.assertEqual(inst.c1[0].a[0].value, inst.c2[0].x[0].value)        
        