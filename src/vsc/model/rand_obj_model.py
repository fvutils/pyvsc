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

from vsc.model.composite_field_model import CompositeFieldModel


class RandObjModel(CompositeFieldModel):
    
    def __init__(self, facade_obj):
        super().__init__(facade_obj, None, True)
        self.is_elab = False;
        self.seed = 1
        self.ref_fields_s = set()
        self.unref_fields_s = set()
        self.level = 0
        self.step = 0
        self.max_step = 10
        self.is_init = False

    def elab(self):
        if self.is_elab:
            return
        self.is_elab = True
        
    def accept(self, visitor):
        visitor.visit_rand_obj(self)
        
        