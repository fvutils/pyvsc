from vsc.model.fieldref_visitor import FieldrefVisitor

#   Copyright 2019 Matthew Ballance
#   All Rights Reserved Worldwide
#
#   Licensed under the Apache License, Version 2.0 (the
#   "License"); you may not use this file except in
#   compliance with the License.  You may obtain a copy of
#   the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in
#   writing, software distributed under the License is
#   distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
#   CONDITIONS OF ANY KIND, either express or implied.  See
#   the License for the specific language governing
#   permissions and limitations under the License.

'''
Created on Jul 23, 2019

@author: ballance
'''
from vsc.constraints import constraint_t
from vsc.types import type_base

import pyboolector
from pyboolector import Boolector
from vsc.model.composite_field_model import CompositeFieldModel


class RandObjModel(CompositeFieldModel):
    
    def __init__(self, facade_obj):
        self.is_elab = False;
        self.seed = 1
        self.level = 0
        
        # Each random object gets its own Boolector instance
        self.btor = Boolector()
        self.btor.Set_opt(pyboolector.BTOR_OPT_INCREMENTAL, True)
        self.btor.Set_opt(pyboolector.BTOR_OPT_MODEL_GEN, True)
        
        print("RandObjModel: " + str(type(facade_obj)))
        super().__init__(facade_obj, None, True, self.btor)

        self.build(self)
    
    def elab(self):
        if self.is_elab:
            return
        
        self.is_elab = True
        
        
    def next(self):
        self.seed ^= (self.seed >> 12)
        self.seed ^= (self.seed << 25)
        self.seed ^= (self.seed >> 27)

        self.seed &= 0xFFFFFFFFFFFFFF
        
        return ((self.seed * 0x4F6CDD1D) >> 16)        

    def swizzle_target_fields_comb(self, target_field_l, bits):
        term = None
        term_valid = False
            
        for t in target_field_l:
            seed = self.next()
            mask = ((1 << bits)-1)
            if t.width() < bits:
                print("  Field smaller than bits")
                const = ((seed >> 7) & ((1 << bits-t.width())-1))
                if (seed & 21) == 0:
                    # Add zeros above
                    tt = self.btor.Concat(self.btor.Const(const, (bits-t.width())), t.get_node())
                else:
                    # Add zeros below
                    tt = self.btor.Concat(t.get_node(), self.btor.Const(const, (bits-t.width())))
                        
            elif t.width() > bits:
                delta = (t.width() - bits)
                offset = (seed % delta)
                print("  Field larger than bits: slice[" + str(offset+bits-1) + ":" + str(offset) + "]")
                # bits=2 ; width=8 ; offset=0 ; 
                tt = self.btor.Slice(t.get_node(), (offset+bits-1), offset)
            else:
                print("  Field same size")
                tt = t.get_node()

            print("Xor: " + str(((seed >> 15) & mask)))
            # >> 2 ^ << 25 ^ >> 27
            tt = self.btor.Xor(tt, self.btor.Const(((seed >> 15) & mask), bits))
                
            if term_valid:
                term = self.btor.Xor(term, tt)
            else:
                term = tt
                term_valid = True
         
        if term_valid:                
            seed = self.next()
            print("Eq: " + str(((seed >> 13) & (bits-1))))
            term = self.btor.Eq(term, self.btor.Const(((seed >> 13) & mask), bits))
            
            self.btor.Assert(term)        

    def swizzle_target_fields(self, target_field_l, bits):
            
        for t in target_field_l:
            seed = self.next()
            mask = ((1 << bits)-1)
            if t.width() < bits:
                print("  Field smaller than bits")
                const = ((seed >> 7) & ((1 << bits-t.width())-1))
#                const = (seed & ((1 << bits-t.width())-1))
                if (seed & 21) == 0:
                    # Add zeros above
                    tt = self.btor.Concat(self.btor.Const(const, (bits-t.width())), t.get_node())
                else:
                    # Add zeros below
                    tt = self.btor.Concat(t.get_node(), self.btor.Const(const, (bits-t.width())))
                        
            elif t.width() > bits:
                delta = (t.width() - bits)
                offset = (seed % delta)
                print("  Field larger than bits: slice[" + str(offset+bits-1) + ":" + str(offset) + "]")
                # bits=2 ; width=8 ; offset=0 ; 
                tt = self.btor.Slice(t.get_node(), (offset+bits-1), offset)
            else:
                print("  Field same size")
                tt = t.get_node()

            print("Xor: " + str(((seed >> 15) & mask)))
            tt = self.btor.Xor(tt, self.btor.Const(((seed >> 15) & mask), bits))
            tt = self.btor.Eq(tt, self.btor.Const(((seed >> 13) & mask), bits))
            self.btor.Assert(tt)

    def swizzle_unreferenced_fields(self, unreferenced_l, bits):
        # Add in pure-random constraints for unreferenced fields
        count = 0
        for t in unreferenced_l:
#            print("Unreferenced: " + t.name())
            seed = self.next()
            const = ((seed >> 13) & ((1 << (t.width())) - 1))
            tt = self.btor.Eq(self.btor.Const(const, t.width()), t.get_node())
#             if t.width() <= bits:
#                 const = (seed & ((1 << t.width()) - 1))
#                 tt = self.btor.Eq(self.btor.Const(const, t.width()), t.get_node())
#             else:
#                 const = (seed & ((1 << bits) - 1))
#                 tt = self.btor.Eq(self.btor.Const(const, t.width()), t.get_node())
                
            self.btor.Assert(tt)        
            count += 1
            
#            if count > 4:
#                break
         
    def do_randomize(self, extra_constraint_l=[]):
        self.pre_randomize()
        
        field_l = []
        self.get_fields(field_l)
        
        self.btor.Pop(self.level)
        self.level = 0
            
        self.btor.Push()
        self.level += 1

        # Collect the constraints and add them to the solver
        constraint_l = []
        self.get_constraints(constraint_l)
        
        node_l = []
        for c in self.constraint_model_l:
            c.get_nodes(node_l)
            
        for c in extra_constraint_l:
            c.build(self)
            c.get_nodes(node_l)
            
        for n in node_l:
            self.btor.Assert(n)
        
        if self.btor.Sat() != self.btor.SAT:
            print("Error: failed")
            return False

        bits = -1
            
        n_target_fields = len(field_l)
        
        sel_l = field_l.copy()
        
        fieldref_v = FieldrefVisitor()
        self.accept(fieldref_v)
           
        # TODO: Now, add in some randomization
            # First, randomly select fields
        target_field_l = []
        unreferenced_l = []
      
        i = 0
        while i < len(sel_l):
            if not sel_l[i] in fieldref_v.ref_s:
                unreferenced_l.append(sel_l.pop(i))
            else:
                i += 1
                
        referenced_l = sel_l.copy()
                
        if len(sel_l) > 4:
            n_target_fields = int(len(sel_l)*2/3)
        elif len(sel_l) > 0:
            n_target_fields = 1
        else:
            n_target_fields = 0
                 
        bits = -1
        if n_target_fields > 0:
            for i in range(n_target_fields):
                seed = self.next()
                idx = ((seed >> 11) % len(sel_l))
#            print("Get rand field: " + str(len(sel_l)) + " " + str(seed%len(sel_l)))
                f = sel_l.pop(idx)
                if f.width() > bits:
                    bits = f.width()
                target_field_l.append(f)
        else:
            bits = 1
            
        if bits > 2:
            bits = int(bits/2)

        rand_fields = ""             
        for f in target_field_l:
            rand_fields += f.f._int_field_info.name + " "

        print("Target Fields: " + rand_fields)

        # First, push constraints for unreferenced fields        
        self.btor.Push()
        self.level += 1
        if len(unreferenced_l) > 0:
            self.swizzle_unreferenced_fields(unreferenced_l, bits)
            
        # Add in pure-random constraints for unreferenced fields
#         for t in unreferenced_l:
# #            print("Unreferenced: " + t.name())
#             seed = self.next()
# #            const = ((seed >> 13) & ((1 << (t.width())) - 1))
#             const = (seed & ((1 << (t.width())) - 1))
#                 
#             tt = self.btor.Eq(self.btor.Const(const, t.width()), t.get_node())
#             self.btor.Assert(tt)

        tries = 0
        if len(target_field_l) > 0:
            success = False
            while bits > 0 and not success:
                self.btor.Push()
                self.level += 1
                
                if len(target_field_l) > 0 and bits > 0:
                    self.swizzle_target_fields(target_field_l, bits)
                 
                if self.btor.Sat() == self.btor.SAT:
                    print("Success")
                    success = True
                else:
                    print("Try again")
                    self.btor.Pop()
                    self.level -= 1
                    bits -= 1
                tries += 1
        else:
            success = True

        if not success:
            print("Failed to randomize")
            self.btor.Sat()
        elif tries > 1:
            print("Success after " + str(tries) + " tries")
            
        # TODO: form a constraint for the FIFO 
        nonrep = None
        nonrep_valid = False
        for f in referenced_l:
            t = self.btor.Ne(f.get_node(), f.get_node())
            print("Ref: " + f.name() + " = " + str(f.f()))
            
            
            # Create a series of xor slices
           
            # term = var[slice] ^ seed[slice]
            
        
        
        self.post_randomize()
#        do_post_randomize()
        
    def accept(self, visitor):
        visitor.visit_rand_obj(self)
        
        