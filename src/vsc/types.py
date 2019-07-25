
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

class field_info():
    def __init__(self):
        self.id = -1
        self.name = None
        self.is_rand = False
        
class type_base():
    
    def __init__(self, width, is_signed):
        self.width = width
        self.is_signed = is_signed
        self.val = 0
        self._int_field_info = field_info()
        
    def __int__(self):
        return self.val
        
        
class bit_t(type_base):
    
    def __init__(self, w=1):
        super().__init__(w, False)
    
def rand_attr(t):
    pass