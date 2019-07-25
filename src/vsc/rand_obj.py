
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
from vsc.impl.ctor import register_rand_obj_type

# TODO: 
def rand_obj(T):
    if not hasattr(T, "_int_rand_info"):
        T._int_rand_info = True
    register_rand_obj_type(T)
    
    return T

class RandObj():
    '''
    Base class for all randomized classes
    '''

    def __init__(self):
        self.is_rand = False

    def randomize(self):
        pass
    
    def randomize_with(self):
        pass
    
    def pre_randomize(self):
        pass
    
    def post_randomize(self):
        pass
        
    