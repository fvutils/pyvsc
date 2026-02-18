'''
Test for coverage sampling on nested rand_attr objects

This test verifies that coverpoints correctly sample nested fields
that are included via vsc.rand_attr in a parent object.

Issue: When a coverpoint targets fields within a nested object decorated with
@vsc.randobj and included via vsc.rand_attr in the item, functional coverage 
is not correctly sampled when using direct field references (without lambda).
'''

import enum
import vsc
from vsc_test_case import VscTestCase


@enum.unique
class Security(enum.IntEnum):
    SEC = 0
    NONSEC = 1
    ROOT = 2


class TestCoverageNestedRandAttr(VscTestCase):
    
    def test_nested_randattr_direct_reference_issue(self):
        """
        Test that demonstrates the issue with direct field references
        on nested rand_attr objects. This test should FAIL with the current
        implementation, showing that direct references don't work correctly.
        """
        
        @vsc.randobj
        class Protection:
            def __init__(self):
                self.security = vsc.rand_enum_t(Security)
        
        @vsc.randobj
        class MyItem:
            def __init__(self):
                self.protection = vsc.rand_attr(Protection())
        
        @vsc.covergroup
        class simple_covergroup:
            def __init__(self):
                self.with_sample(dict(it=MyItem()))
                
                # Direct reference - this currently FAILS (binds to initial value)
                self.security_cp_direct = vsc.coverpoint(
                    self.it.protection.security,
                    bins={s.name: vsc.bin(s.value) for s in Security}
                )
        
        # Create covergroup and sample multiple times
        cg = simple_covergroup()
        item = MyItem()
        
        # Track which values we've seen during randomization
        seen_values = set()
        
        # Sample many times to ensure we hit all values
        for _ in range(100):
            item.randomize()
            cg.sample(item)
            seen_values.add(item.protection.security)
        
        # We should have seen all three security values
        self.assertEqual(len(seen_values), 3, 
                        f"Expected to see all 3 Security values, but only saw: {seen_values}")
        
        # Check coverage - each bin should have been hit
        model = cg.security_cp_direct.get_model()
        
        # Get hit counts for each bin using the hit_l list
        bins_hit = 0
        for hit_count in model.hit_l:
            if hit_count > 0:
                bins_hit += 1
        
        # With the bug, only the first bin (SEC=0) will be hit
        # After the fix, all 3 bins should be hit
        self.assertEqual(bins_hit, 3,
                        f"Expected all 3 bins to be hit, but only {bins_hit} were hit")
    
    def test_nested_randattr_lambda_workaround(self):
        """
        Test that demonstrates the workaround using lambda expressions.
        This test should PASS even with the current implementation.
        """
        
        @vsc.randobj
        class Protection:
            def __init__(self):
                self.security = vsc.rand_enum_t(Security)
        
        @vsc.randobj
        class MyItem:
            def __init__(self):
                self.protection = vsc.rand_attr(Protection())
        
        @vsc.covergroup
        class simple_covergroup:
            def __init__(self):
                self.with_sample(dict(it=MyItem()))
                
                # Lambda reference - this WORKS
                self.security_cp_lambda = vsc.coverpoint(
                    lambda: self.it.protection.security,
                    cp_t=vsc.enum_t(Security),
                    bins={s.name: vsc.bin(s.value) for s in Security}
                )
        
        # Create covergroup and sample multiple times
        cg = simple_covergroup()
        item = MyItem()
        
        # Track which values we've seen during randomization
        seen_values = set()
        
        # Sample many times to ensure we hit all values
        for _ in range(100):
            item.randomize()
            cg.sample(item)
            seen_values.add(item.protection.security)
        
        # We should have seen all three security values
        self.assertEqual(len(seen_values), 3,
                        f"Expected to see all 3 Security values, but only saw: {seen_values}")
        
        # Check coverage - each bin should have been hit
        model = cg.security_cp_lambda.get_model()
        
        # Get hit counts for each bin using the hit_l list
        bins_hit = 0
        for hit_count in model.hit_l:
            if hit_count > 0:
                bins_hit += 1
        
        # All 3 bins should be hit with lambda
        self.assertEqual(bins_hit, 3,
                        f"Expected all 3 bins to be hit, but only {bins_hit} were hit")
    
    def test_non_nested_direct_reference_works(self):
        """
        Test that direct references work correctly for non-nested fields.
        This should PASS and demonstrates that the issue is specific to nested fields.
        """
        
        @vsc.randobj
        class MyItem:
            def __init__(self):
                self.security = vsc.rand_enum_t(Security)
        
        @vsc.covergroup
        class simple_covergroup:
            def __init__(self):
                self.with_sample(dict(it=MyItem()))
                
                # Direct reference to non-nested field - this WORKS
                self.security_cp = vsc.coverpoint(
                    self.it.security,
                    bins={s.name: vsc.bin(s.value) for s in Security}
                )
        
        # Create covergroup and sample multiple times
        cg = simple_covergroup()
        item = MyItem()
        
        # Track which values we've seen during randomization
        seen_values = set()
        
        # Sample many times to ensure we hit all values
        for _ in range(100):
            item.randomize()
            cg.sample(item)
            # item.security is directly the Security enum value
            seen_values.add(item.security)
        
        # We should have seen all three security values
        self.assertEqual(len(seen_values), 3,
                        f"Expected to see all 3 Security values, but only saw: {seen_values}")
        
        # Check coverage - each bin should have been hit
        model = cg.security_cp.get_model()
        
        # Get hit counts for each bin using the hit_l list
        bins_hit = 0
        for hit_count in model.hit_l:
            if hit_count > 0:
                bins_hit += 1
        
        # All 3 bins should be hit for non-nested fields
        self.assertEqual(bins_hit, 3,
                        f"Expected all 3 bins to be hit, but only {bins_hit} were hit")
