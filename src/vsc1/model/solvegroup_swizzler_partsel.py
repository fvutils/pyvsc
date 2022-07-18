'''
Created on Sep 18, 2021

@author: mballance
'''

from vsc1.model.bin_expr_type import BinExprType
from vsc1.model.expr_bin_model import ExprBinModel
from vsc1.model.expr_fieldref_model import ExprFieldRefModel
from vsc1.model.expr_literal_model import ExprLiteralModel
from vsc1.model.expr_model import ExprModel
from vsc1.model.expr_partselect_model import ExprPartselectModel
from vsc1.model.field_scalar_model import FieldScalarModel
from vsc1.model.variable_bound_model import VariableBoundModel


class SolveGroupSwizzlerPartsel(object):
    
    def __init__(self, randstate, solve_info):
        self.debug = 0
        self.randstate = randstate
        self.solve_info = solve_info
    
    def swizzle(self, 
                btor, 
                rs, 
                bound_m):
        if self.debug > 0:
            print("--> swizzle_randvars")

        swizzled_field = False
        # For each random variable, select a partition with it's known 
        # domain and add the corresponding constraint
        field_l = rs.rand_fields()
            
        if self.debug > 0:
            print("  " + str(len(field_l)) + " fields in randset")
            
        if rs.rand_order_l is not None:
            # Perform an ordered randomization
            for ro_l in rs.rand_order_l:
                swizzled_field |= self.swizzle_field_l(ro_l, rs, bound_m, btor)
        else:
            swizzled_field |= self.swizzle_field_l(rs.rand_fields(), rs, bound_m, btor)
                
        if not swizzled_field:
            if self.solve_info is not None:
                self.solve_info.n_sat_calls += 1                    
            btor.Sat()
            
        if self.debug > 0:
            print("<-- swizzle_randvars")    
            
    def swizzle_field_l(self, field_l, rs, bound_m, btor):
        e = None
        if len(field_l) > 0:
            # Make a copy of the field list so we don't
            # destroy the original
            field_l = field_l.copy()
            
            swizzle_node_l = []
            swizzle_expr_l = []
            max_swizzle = 4

            # Select up to `max_swizzle` fields to swizzle            
            for i in range(max_swizzle):
                if len(field_l) > 0:
                    field_idx = self.randstate.randint(0, len(field_l)-1)
                    f = field_l.pop(field_idx)
                    e_l = self.swizzle_field(f, rs, bound_m)
                    if e_l is not None:
                        swizzle_expr_l.append(e_l)
                        n_l = []
                        for e in e_l:
                            n_l.append(e.build(btor))
                        swizzle_node_l.append(n_l)
                else:
                    break

            # Each entry in the nodelist corresponds to a field
            for field_nl in swizzle_node_l:
                # Start by assuming all
                for n in field_nl:
                    btor.Assume(n)

                if self.solve_info is not None:
                    self.solve_info.n_sat_calls += 1
                if btor.Sat() != btor.SAT:
                    # Add one at a time, preserving those that are SAT

                    for n in field_nl:
                        btor.Assume(n)
                        if btor.Sat() == btor.SAT:
                            btor.Assert(n)
                            
#                    if self.debug > 0:
#                        print("Randomization constraint failed. Removing last: %s" %
#                              self.pretty_printer.print(e))
                else:
                    # Randomization constraints succeeded. Go ahead and assert
                    for n in field_nl:
                        btor.Assert(n)
                    
            if self.solve_info is not None:
                self.solve_info.n_sat_calls += 1
            if btor.Sat() != btor.SAT:
                raise Exception("failed to add in randomization (2)")                           
            return True
        else:
            return False            

    def swizzle_field(self, f, rs, bound_m) -> ExprModel:
        ret = None
        
        if self.debug > 0:
            print("Swizzling field %s" % f.name)
             
        if f in rs.dist_field_m.keys():
            if self.debug > 0:
                print("Note: field %s is in dist map" % f.name)
                for d in rs.dist_field_m[f]:
                    print("  Target interval %d" % d.target_range)
            if len(rs.dist_field_m[f]) > 1:
                target_d = self.randstate.randint(0, len(rs.dist_field_m[f])-1)
                dist_scope_c = rs.dist_field_m[f][target_d]
            else:
                dist_scope_c = rs.dist_field_m[f][0]
                
            target_w = dist_scope_c.dist_c.weights[dist_scope_c.target_range]
            if target_w.rng_rhs is not None:
                # Dual-bound range
                val_l = target_w.rng_lhs.val()
                val_r = target_w.rng_rhs.val()
                val = self.randstate.randint(val_l, val_r)
                if self.debug > 0:
                    print("Select dist-weight range: %d..%d ; specific value %d" % (
                        int(val_l), int(val_r), int(val)))
                ret = [ExprBinModel(
                    ExprFieldRefModel(f),
                    BinExprType.Eq,
                    ExprLiteralModel(val, f.is_signed, f.width))]
            else:
                # Single value
                val = target_w.rng_lhs.val()
                ret = [ExprBinModel(
                    ExprFieldRefModel(f),
                    BinExprType.Eq,
                    ExprLiteralModel(int(val), f.is_signed, f.width))]
        else:
            if f in bound_m.keys():
                f_bound = bound_m[f]
                if not f_bound.isEmpty():
                    ret = self.create_rand_domain_constraint(f, f_bound)
                    
        return ret
    
    def create_rand_domain_constraint(self, 
                f : FieldScalarModel, 
                bound_m : VariableBoundModel)->ExprModel:
        e = []
        range_l = bound_m.domain.range_l
        
        if self.debug:
            print("range_l: %d (%s)" % (len(range_l), str(range_l)))
        if len(range_l) > 1:
            # If we have a multi-part domain, select from one 
            # of the slices
            range_idx = self.randstate.randint(0, len(range_l)-1)
            t_range = range_l[range_idx]
        else:
            # Otherwise, if our domain is a single range, select
            # an appropriate value and slice it into selections
            t_range = range_l[0]
            
        if self.debug > 0:
            print("Domain: %d..%d" % (t_range[0], t_range[1]))
        if t_range[0] == t_range[1]:
            # Single value
            e.append(ExprBinModel(
                        ExprFieldRefModel(f),
                        BinExprType.Eq,
                        ExprLiteralModel(t_range[0], False, 32)))
        else:
            # Determine the max width to use for swizzling. 
            # max value of abs bounds

            maxval = int(max(abs(t_range[0]), abs(t_range[1])))

            d_width = 0
            
            while maxval > 0:
                d_width += 1
                maxval >>= 1
    
            if self.debug > 0:
                print("d_width: %d" % d_width)                
                
            bit_pattern = self.randstate.randint(t_range[0], t_range[1])
            e = self._build_swizzle_constraints(f, bit_pattern, d_width)

        return e
    
    def _build_swizzle_constraints(self, f, bit_pattern, d_width):
        e = []
        max_intervals = 6

        if self.debug > 0:            
            print("bit_pattern: %s" % bin(bit_pattern))
        
        if d_width > max_intervals:
            interval_w = int(d_width/max_intervals)
            
            for i in range(max_intervals):
                low = i*interval_w
                
                if i+1 == max_intervals:
                    high = d_width-1
                    width = d_width-low
                else:
                    high = (i+1)*interval_w-1
                    width = interval_w

                if self.debug > 0:
                    print("%d..%d 0x%08x" % (
                        low, high, ((bit_pattern >> low) & ((1 << width)-1))))
                e.append(ExprBinModel(
                    ExprPartselectModel(
                        ExprFieldRefModel(f),
                        ExprLiteralModel(high, False, 32),
                        ExprLiteralModel(low, False, 32)),
                    BinExprType.Eq,
                    ExprLiteralModel((bit_pattern >> low) & ((1 << width)-1), False, width)
                    ))
        else:
            # Create a per-bit constraint            
            for i in range(d_width):
                e.append(ExprBinModel(
                    ExprPartselectModel(
                        ExprFieldRefModel(f),
                        ExprLiteralModel(i, False, 32)),
                    BinExprType.Eq,
                    ExprLiteralModel((bit_pattern >> i) & 1, False, 1)
                    ))        
        return e

