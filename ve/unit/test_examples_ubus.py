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
from enum import Enum, auto, IntEnum


class TestExamplesUbus(VscTestCase):
    
    def test_ubus(self):
        
        class ubus_read_write_enum(IntEnum):
            READ = auto()
            WRITE = auto()

        @vsc.randobj        
        class ubus_transfer(object):
            
            def __init__(self):
#                self.addr = vsc.rand_bit_t(16)
                self.addr = vsc.rand(vsc.bit_t(16))
                self.read_write = vsc.rand_enum_t(ubus_read_write_enum)
                self.size = vsc.rand_bit_t(32)
                self.data = vsc.randsz_list_t(vsc.uint8_t())
                self.wait_state = vsc.randsz_list_t(vsc.bit_t(4))
                self.error_pos = vsc.rand_bit_t(32)
                self.transmit_delay = vsc.rand_bit_t(32)
                self.master = ""
                self.slave = ""

            @vsc.constraint
            def c_read_write(self):
                self.read_write in vsc.rangelist(
                    ubus_read_write_enum.READ, 
                    ubus_read_write_enum.WRITE)

#            @vsc.constraint
#            def c_read_write(self):
#                self.read_write == ubus_read_write_enum.READ
                
            @vsc.constraint
            def c_size(self):
                self.size in vsc.rangelist(1,2,4,8)

            @vsc.constraint
            def c_data_wait_size(self):
                self.data.size == self.size;
                self.wait_state.size == self.size;

            @vsc.constraint
            def c_transmit_delay(self):
                self.transmit_delay <= 10

        xfer = ubus_transfer()

        size_bins = [0]*4
        transmit_delay_bins = [0]*11

        import time
        count = 1000
#        count = 1
        start_m = int(round(time.time() * 1000))

        for i in range(count):
            xfer.randomize()
            print("read_write=%s size=%d transmit_delay=%d addr=%x" % (str(xfer.read_write), xfer.size, xfer.transmit_delay, xfer.addr))
            if xfer.size == 1:
                size_bins[0] += 1
            elif xfer.size == 2:
                size_bins[1] += 1
            elif xfer.size == 4:
                size_bins[2] += 1
            elif xfer.size == 8:
                size_bins[3] += 1
            transmit_delay_bins[xfer.transmit_delay] += 1
        end_m = int(round(time.time() * 1000))
        
        delta_m = (end_m-start_m)
        count_per_s = (count*1000)/delta_m
        ms_per_i = (delta_m/count)
       
        print("Delta: " + str(delta_m)) 
        print("Items/s: " + str(count_per_s) + " Time/item (ms): " + str(ms_per_i))
            
        print("size_bins: " + str(size_bins))
        print("transmit_delay_bins: " + str(transmit_delay_bins))
        
        for i in range(len(size_bins)):
            self.assertGreater(size_bins[i], 0)
            
        for i in range(len(transmit_delay_bins)):
            self.assertGreater(transmit_delay_bins[i], 0)
            
#        for i in range(100):
#            with xfer.randomize_with() as it:
#                it.size == 1
#            print("size=%d transmit_delay=%d addr=%x" % (xfer.size, xfer.transmit_delay, xfer.addr))
