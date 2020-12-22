'''
Created on Dec 20, 2020

@author: mballance
'''
import vsc
from vsc_test_case import VscTestCase

class TestExtArray(VscTestCase):
    
    def test_ext_array_1(self):
        
        @vsc.randobj
        class region_c(object):
            
            def __init__(self, 
                         name="",
                         size_in_bytes=-1,
                         xwr=0):
                self.name = name
                self.size_in_bytes = vsc.uint32_t(i=size_in_bytes)
                self.xwr = xwr = vsc.uint8_t(i=xwr)

        @vsc.randobj
        class cfg_c(object):
            
            def __init__(self):
                self.mem_region = vsc.list_t(region_c())
                self.mem_region.extend([
                    region_c(name="region_0", size_in_bytes=4096, xwr=8),
                    region_c(name="region_1", size_in_bytes=4096, xwr=8)
                    ])
                self.amo_region = vsc.list_t(region_c())
                self.amo_region.extend([
                    region_c(name="amo_0", size_in_bytes=64, xwr=8)
                    ])
                self.s_mem_region = vsc.list_t(region_c())
                self.s_mem_region.extend([
                    region_c(name="s_region_0", size_in_bytes=4096, xwr=8),
                    region_c(name="s_region_1", size_in_bytes=4096, xwr=8)
                    ])
                
        @vsc.randobj
        class mem_access_stream_c(object):
            
            def __init__(self, cfg):
                self.cfg = cfg
                self.max_data_page_id = vsc.int32_t()
                self.load_store_shared_memory = False
                self.kernel_mode = False
                self.data_page = vsc.list_t(region_c())
                self.data_page_id = vsc.rand_uint16_t()
                self.max_load_store_offset = vsc.rand_uint32_t()
            
                
            def pre_randomize(self):
                self.data_page.clear()
                if self.load_store_shared_memory:
                    self.data_page.extend(self.cfg.amo_region)
                elif self.kernel_mode:
                    self.data_page.extend(self.cfg.s_mem_region)
                else:
                    self.data_page.extend(self.cfg.mem_region)
                self.max_data_page_id = len(self.data_page)
                
            @vsc.constraint
            def addr_c(self):
                self.data_page_id < self.max_data_page_id
                with vsc.foreach(self.data_page, idx=True) as i:
                    with vsc.if_then(i == self.data_page_id):
                        self.max_load_store_offset == self.data_page[i].size_in_bytes
                        

        cfg = cfg_c()
        it = mem_access_stream_c(cfg)
        
        it.randomize()
        print("len(data_page): " + str(len(it.data_page)))
        print("max_data_page_id=" + str(it.max_data_page_id) + " data_page_id=" + str(it.data_page_id))
        print("max_load_store_offset=" + str(it.max_load_store_offset))
        
            
        
        