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

from builtins import set
from typing import Set, List

from vsc.model.constraint_model import ConstraintModel
from vsc.model.field_model import FieldModel


class RandSet(object):
    """Contains information about one set of related fields and constraints"""
    
    def __init__(self):
        self.field_s : Set[FieldModel] = set()
        # Related fields that shouldn't be targeted for randomization
        self.dnr_field_s : Set[FieldModel] = set()
        self.constraint_s :Set[ConstraintModel] = set()
        self.field_l = None
        self.field_rand_l = None
        self.all_field_l = None
        
    def add_field(self, f):
        self.field_s.add(f)
        
    def add_dnr_field(self, f):
        self.dnr_field_s.add(f)
        
    def fields(self):
        return self.field_s
    
    def fields_l(self):
        if self.field_l is None:
            self.field_rand_l = []
            self.field_l = []
            for f in self.field_s:
                if f.is_used_rand:
                    self.field_rand_l.append(f)
                self.field_l.append(f)
        return self.field_l
    
    def rand_fields(self):
        if self.field_rand_l is None:
            self.field_rand_l = []
            self.field_l = []
            for f in self.field_s:
                if f.is_used_rand:
                    self.field_rand_l.append(f)
                self.field_l.append(f)
        return self.field_rand_l
    
    def dnr_fields(self):
        return self.dnr_field_s
    
    def all_fields(self)->List[FieldModel]:
        if self.all_field_l is None:
            self.all_field_l = list(self.field_s)
            self.all_field_l.extend(list(self.dnr_field_s))
            
        return self.all_field_l
        
        
    def add_constraint(self, c):
        self.constraint_s.add(c)
        
    def constraints(self) ->Set[ConstraintModel]:
        return self.constraint_s
    
