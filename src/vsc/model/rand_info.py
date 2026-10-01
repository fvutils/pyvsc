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


# Created on Jan 22, 2020
#
# @author: ballance


from vsc.model.rand_set import RandSet
from typing import List
from vsc.model.field_model import FieldModel


class RandInfo(object):
    """Contains information about a set of variables and constraints"""
    
    def __init__(self, randset_l, unconstrained_l, floating_constraint_l = []):
        self.randset_l :List[RandSet] = randset_l
        self.unconstrained_l :List[FieldModel] = unconstrained_l
        self.floating_constraint_l = floating_constraint_l
        # RandSets promoted to the T0 no-solver tier: their fields have been
        # appended to unconstrained_l and they are no longer solved. Retained
        # because the plan cache builds its freshness signature from the fields
        # and constraints the RandSets reference -- dropping them would stop it
        # noticing a change that invalidates a promoted field's domain.
        self.t0_randset_l :List[RandSet] = []
        
    def add_randset(self, r : RandSet):
        self.randset_l.append(r)
        
    def randsets(self) ->List[RandSet]:
        return self.randset_l

    def all_randsets(self) ->List[RandSet]:
        """Every RandSet the build produced, solved or T0-promoted. Use this
        (not randsets()) for anything that reasons about the *model* rather than
        about what the solver is asked to do."""
        if not self.t0_randset_l:
            return self.randset_l
        return self.randset_l + self.t0_randset_l
        
    def add_field(self, f:FieldModel):
        self.unconstrained_l.append(f)
        
    def unconstrained(self)->List[FieldModel]:
        return self.unconstrained_l
        