from vsc.model.expr_model import ExprModel

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
Created on Jul 26, 2019

@author: ballance
'''

class ExprFieldRefModel(ExprModel):
    
    def __init__(self, fm):
        self.fm = fm

    def build(self, builder):
        pass
        
    def get_node(self):
        return self.fm.get_node()
    
    def is_signed(self):
        return self.fm.f.is_signed
    
    def width(self):
        return self.fm.f.width