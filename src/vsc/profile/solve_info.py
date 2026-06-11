'''
Created on Jul 3, 2021

@author: mballance
'''

class SolveInfo(object):
    
    def __init__(self):
        self.totaltime = 0
        # Number of randsets
        self.n_randsets = 0
        
        # Constrained fields
        self.n_cfields = 0

        # Time establishing SAT-ness        
        self.sat_time = 0

        # Time swizzling random fields        
        self.rnd_time = 0
        
        self.n_sat_calls = 0

        # Number of RandSets that fell back from the primary back-end to
        # another (e.g. dv-solve -> Boolector) because of BackendIncomplete.
        self.n_fallbacks = 0

        # Per-reason fallback tally keyed by BackendIncomplete.reason_code
        # (e.g. {"dist": 0, "array": 2, "width": 1}). Drives the per-phase
        # burn-down (see the feature-completeness plan, Phase 0).
        self.fallback_reasons = {}

        pass

    def add_fallback(self, reason_code):
        """Record a fallback by its reason code."""
        self.n_fallbacks += 1
        self.fallback_reasons[reason_code] = \
            self.fallback_reasons.get(reason_code, 0) + 1