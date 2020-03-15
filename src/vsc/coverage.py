# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import enum
from vsc.model.coverpoint_bin_enum_model import CoverpointBinEnumModel
from vsc.model import expr_mode, get_expr_mode, enter_expr_mode, leave_expr_mode,\
    get_expr_mode_depth
from vsc.impl.covergroup_int import CovergroupInt
from vsc.impl.options import Options
from vsc.impl.type_options import TypeOptions
from vsc.model.expr_ref_model import ExprRefModel
from vsc.model.scalar_field_model import ScalarFieldModel
from vsc.model.composite_field_model import CompositeFieldModel
from vsc.impl import ctor
import inspect
from vsc.model.source_info import SourceInfo
from vsc.impl.coverage_registry import CoverageRegistry
'''
Created on Aug 3, 2019

@author: ballance
'''
# marks 

from enum import Enum, auto

from vsc.impl.ctor import pop_expr
from vsc.model.covergroup_model import CovergroupModel
from vsc.model.coverpoint_bin_array_model import CoverpointBinArrayModel
from vsc.model.coverpoint_bin_collection_model import CoverpointBinCollectionModel
from vsc.model.coverpoint_bin_model import CoverpointBinModel
from vsc.model.coverpoint_cross_model import CoverpointCrossModel
from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.rangelist_model import RangelistModel
from vsc.types import rangelist, bit_t, to_expr, type_base


def covergroup(T):
    """Covergroup decorator marks as class as being a covergroup"""
    
    if not hasattr(T, "_cg_init"):
        def dump(self, ind=""):
            model = self.get_model()
            model.dump(ind)
            
        # TODO: Make adding sample parameters additive?
        def with_sample(self, params):
            model = self.get_model()
            cg_i = self._get_int()
            for pn,pt in params.items():
                print("parameter: " + pn)
                pm = pt.build_field_model(pn)
                setattr(self, pn, pt)
                cg_i.sample_var_l.append(pn)
                
                # Add a field to the covergroup model
                model.add_field(pm)
                
            print("self=" + str(self) + " sample_var_l=" + str(len(cg_i.sample_var_l)))
                
        def sample(self, *args, **kwargs):
            """Base sampling method that samples all coverpoints and crosses"""
            # Build the model if we haven't yet
            cg_i = self._get_int()
            
            # TODO: Need to propagate values to base classes
            model = self.get_model()
            
            sample_var_len = len(cg_i.sample_var_l)
            
            if len(args) != sample_var_len:
                raise Exception("Wrong number of parameters: expect " + str(sample_var_len) + " receive " + str(len(args)))

            model = self.get_model()        
            for i in range(len(args)):
                # TODO: need to account for inheritance
                ex_f = model.get_field(i)
                if isinstance(ex_f, CompositeFieldModel):
                    # TODO: probably need to do something a bit more than this?
                    model.set_field(i, args[i].get_model())
                elif isinstance(ex_f, ScalarFieldModel):
                    if isinstance(args[i], type_base):
                        ex_f.set_val(args[i].get_val())
                    else:
                        ex_f.set_val(int(args[i]))
                    
                setattr(self, cg_i.sample_var_l[i], args[i])
#                getattr(self, cg_i.sample_var_l[i]).set_val(args[i])

            model.sample()

        pass
        
        def get_coverage(self):
            return self.get_model().get_coverage()
        
        def get_inst_coverage(self):
            return self.get_model().get_inst_coverage()
        
        def get_model(self):
            cg_i = self._get_int()
            if cg_i.model is None:
                cg_i.model = CovergroupModel(T.__name__)
            
            return cg_i.model
        
        def build_model(self):
            cg_i = self._get_int()
            self.get_model()
            
            obj_name_m = {}
            for n in dir(self):
                obj = getattr(self, n)
                if hasattr(obj, "build_cov_model"):
                    obj_name_m[obj] = n
                    
            for b in self.buildable_l:
                print("b: " + str(b))
          
                cp_m = b.build_cov_model(cg_i.model, obj_name_m[b])
                cg_i.model.add_coverpoint(cp_m)
                
            # Register the covergroup in the registry. This will ensure that
            # this coverage instance is properly connected to the type coverage
            # If the instance covergroup happens to be parameterized,
            # then the type covergroup must have the same parameterization
            CoverageRegistry.inst().register_cg(self.get_model())
            
                
            # We're done, so lock the covergroup
            self.lock()

            # Finalize the contents of the covergroup                
            cg_i.model.finalize()
            
        
        def _get_int(self):
            if not hasattr(self, "_cg_int"):
                self._cg_int = CovergroupInt(self)
            return self._cg_int
        
        def lock(self):
            cg_i = self._get_int()
            cg_i.locked = True
            self.options.lock()
            self.type_options._lock()
        
        def _setattr(self, field, val):
            if hasattr(val, "build_cov_model"):
                if not hasattr(self, "buildable_l"):
                    object.__setattr__(self, "buildable_l", [])
                self.buildable_l.append(val)
            object.__setattr__(self, field, val)
        
        setattr(T, "dump", dump)
        setattr(T, "with_sample", with_sample)
        setattr(T, "sample", sample)
        setattr(T, "get_coverage", get_coverage)
        setattr(T, "get_inst_coverage", get_inst_coverage)
        setattr(T, "get_model", get_model)
        setattr(T, "build_model", build_model)
        setattr(T, "_get_int", _get_int)
        setattr(T, "lock", lock)
        setattr(T, "__setattr__", _setattr)
        setattr(T, "_cg_init", True)
        
    # Store declaration information on the type
    file = inspect.getsourcefile(T)
    lineno = inspect.getsourcelines(T)[1]
    setattr(T, "_srcinfo_decl", SourceInfo(file, lineno))

    # This is the interposer class that wraps a user-defined
    # covergroup class. It ensures that the coverage model is
    # created while field refs are treated as expressions
    class covergroup_interposer(T):
        
        def __init__(self, *args, **kwargs):
            cg_i = self._get_int()
            
            print("covergroup_inst: " + str(type(self)))
            frame = inspect.stack()[1]
            print("  Created: " + frame.filename + ":" + str(frame.lineno))
            print("  Declared: " + str(type(self)._srcinfo_decl))
#            module = inspect.getmodule(frame[0])
#            print("frame=" + str(frame) + " module=" + str(module))
#             file = inspect.getsourcefile(self)
#             lines = inspect.getsourcelines(T)
#             print("lines:\n" + str(lines))
#             lineno = lines[1]
#             print("  source: " + file + ":" + str(lineno))

            self.buildable_l = []
            
            # Construct the model            
            self.get_model()
            
            # Ensure options/type_options created before 
            # calling (user) base-class __init__
            if not hasattr(self, "options"):
                self.options = Options()
            if not hasattr(self, "type_options"):
                self.type_options = TypeOptions()
                
            for a in args:
                if hasattr(a, "_ro_init"):
                    # Ensure the model is constructed
                    a.get_model()

            with cg_i:                
                super().__init__(*args, **kwargs)

            if cg_i.ctor_level == 0:
                # TODO: need to actually elaborate the model
                self.build_model()
    
    ret = type(T.__name__, (covergroup_interposer,), dict())
    
    return ret

        
class bin(object):
    def __init__(self, *args):
        self.range_l = args
        
    def build_cov_model(self, parent, name):
        # Construct a range model
        range_l = RangelistModel(self.range_l)
        return CoverpointBinModel(name, range_l)
        

class bin_array(object):
    
    def __init__(self, nbins, *args):
        self.nbins = nbins
        self.range_l = args
        
        if len(args) == 0:
            raise Exception("No bins range specified")
    
    def build_cov_model(self, parent, name):
        ret = CoverpointBinCollectionModel(name)
        
        # First, need to determine how many total bins
        # Construct a range model
        if len(self.nbins) == 0:
            # unlimited number of bins
            for r in self.range_l:
                if isinstance(r, list):
                    if len(r) != 2: 
                        raise Exception("Expecting range \"" + str(r) + "\" to have two elements")
                    ret.add_bin(CoverpointBinArrayModel(name, r[0], r[1]))
                else:
                    raise Exception("Single-value bins unimplemented")
        else:
            # TODO: Calculate number of values
            # TODO: Calculate values per bin
            print("TODO: limited-value bins")
            pass                    

        return ret
    
class binsof(object):
    # TODO: future implementation of the 'binsof' operator
    
    def __init__(self, cp):
        pass
    

    def intersect(self, rng):
        pass

    def __and__(self, rhs):
        pass
    
    def __not__(self, rhs):
        pass
    
    def __or__(self, rhs):
        pass
    
class coverpoint(object):
   
    def __init__(self, target, cp_t=None, iff=None, bins=None, options=None, type_options=None):
        self.have_var = False
        self.target = None
        self.model = None
        self.target_kind = None
        self.target_type = None
        self.get_val_f = None
        self.options = Options()
        self.type_options = TypeOptions()
        
        ctor.clear_exprs()
        
        if options is not None:
            self.options.set(options)
            
        if type_options is not None:
            self.type_options.set(type_options)

        with expr_mode():
            print("target=" + str(target))
            if isinstance(target, type_base):
                self.have_var = True
                self.target = target.to_expr().em
                self.cp_t = type_base
            elif callable(target):
#             if cp_t is None:
#                 raise Exception("Coverpoint with a callable target must specify type")

                self.cp_t = cp_t
            
                self.target = target
                self.get_val_f = target
            else:
                # should be an actual variable (?)
                # TODO: or, could be an expression
                print("TODO: handle actual variables")
                to_expr(target)
                self.target = pop_expr()
                print("target=" + str(self.target))
                self.get_val_f = self.target.val
                print("self.get_val_f=" + str(self.get_val_f))
            
        self.iff = iff
        self.bins = bins
        
        ctor.clear_exprs()
        
    def get_coverage(self):
        if self.model is None:
            return 0.0
        else:
            return self.model.get_coverage()
    
    def get_inst_coverage(self):
        if self.model is None:
            return 0.0
        else:
            return self.model.get_inst_coverage()
    
    def build_cov_model(self, parent, name):
        if self.model is None:
            if self.get_val_f is not None:
                if self.cp_t is not None and isinstance(self.cp_t, type_base):
                    width = self.cp_t.width
                    is_signed = self.cp_t.is_signed
                else:
                    width = 32
                    is_signed = True
                    
                sample_expr = ExprRefModel(
                    self.get_val_f, 
                    width,
                    is_signed)
            else:
                sample_expr = self.target
            
            self.model = CoverpointModel(
                sample_expr,
                name)

            with expr_mode():
                if self.bins is None or len(self.bins) == 0:
                    if self.bins is None or len(self.bins) == 0:
                        if self.cp_t == type_base:
                            print("TODO: auto-bins from explicit type")
                    elif type(self.cp_t) == enum.EnumMeta:
                        for e in list(self.cp_t):
                            self.model.add_bin_model(CoverpointBinEnumModel(e.name, e))
                    else:
                        raise Exception("attempting to create auto-bins from unknown type " + str(self.cp_t))                       
                else:
                    for bin_name,bin_spec in self.bins.items():
                        if not hasattr(bin_spec, "build_cov_model"):
                            raise Exception("Bin specification doesn't have a build_cov_model method")
                        print("bin: " + bin_name + " spec=" + str(bin_spec))
                        bin_m = bin_spec.build_cov_model(self.model, bin_name)
                        self.model.add_bin_model(bin_m)
         
        print("coverpoint::build_cov_model: " + str(self) + " " + str(self.model))
        return self.model
    
    def get_model(self):
        return self.model
    
    def get_val(self, cp_m):
        ret = int(self.get_val_f())

        return ret
    
    def set_val(self, val):
        self.target.set_val(val)
    
    def __le__(self, rhs):
        if self.have_var:
            self.target(rhs)
        else:
            raise Exception("Attempting to set value of non-variable coverpoint")
        
    def _lock(self):
        self.options.lock()
        self.type_options._lock()
    
class cross(object):
    
    def __init__(self, target_l, bins=None):
        for t in target_l:
            if not isinstance(t, coverpoint):
                raise Exception("Cross target \"" + str(t) + "\" is not a coverpoint")
        self.target_l = target_l
        self.bins = bins
        
    def build_cov_model(self, parent, name):
        ret = CoverpointCrossModel(name)
        
        for cp in self.target_l:
            m = cp.get_model()
            ret.add_coverpoint(m)
            
        return ret
