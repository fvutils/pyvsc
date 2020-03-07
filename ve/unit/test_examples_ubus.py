from vsc_test_case import VscTestCase

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
Created on Jan 23, 2020

@author: ballance
'''
from unittest.case import TestCase

import vsc
from vsc.types import rand_enum_t, rand_bit_t, rangelist
from enum import Enum, auto


class TestExamplesUbus(VscTestCase):
    
    def test_ubus(self):
        
        class ubus_read_write_enum(Enum):
            READ = auto()
            WRITE = auto()

        @vsc.randobj        
        class ubus_transfer(object):
            
            def __init__(self):
                self.addr = rand_bit_t(16)
                self.read_write = rand_enum_t(ubus_read_write_enum)
                self.size = rand_bit_t(32)
#                rand bit [7:0]            data[];
#                rand bit [3:0]            wait_state[];
                self.error_pos = rand_bit_t(32)
                self.transmit_delay = rand_bit_t(32)
                self.master = ""
                self.slave = ""

#             @vsc.constraint
#             def c_read_write(self):
#                 self.read_write in rangelist(
#                     ubus_read_write_enum.READ, 
#                     ubus_read_write_enum.WRITE)

            @vsc.constraint
            def c_size(self):
                self.size in rangelist(1,2,4,8)

#            constraint c_data_wait_size {
#                data.size() == size;
#                wait_state.size() == size;

            @vsc.constraint
            def c_transmit_delay(self):
                self.transmit_delay <= 10

        xfer = ubus_transfer()
        for i in range(100):
            xfer.randomize()
            print("size=%d transmit_delay=%d addr=%x" % (xfer.size, xfer.transmit_delay, xfer.addr))
            
        for i in range(100):
            with xfer.randomize_with() as it:
                it.size == 1
            print("size=%d transmit_delay=%d addr=%x" % (xfer.size, xfer.transmit_delay, xfer.addr))
