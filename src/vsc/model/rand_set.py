
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

'''
Created on Jan 22, 2020

@author: ballance
'''
from builtins import set

class RandSet(object):
    """Contains information about one set of related fields and constraints"""
    
    def __init__(self):
        self.field_s = set()
        self.constraint_s = set()
        
    def add_field(self, f):
        self.field_s.add(f)
        
    def fields(self):
        return self.field_s
        
    def add_constraint(self, c):
        self.constraint_s.add(c)
        
    def constraints(self):
        return self.constraint_s
        
        