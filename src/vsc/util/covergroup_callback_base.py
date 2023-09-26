#****************************************************************************
#* covergroup_callback_base.py
#*
#* Copyright 2022 Matthew Ballance and Contributors
#*
#* Licensed under the Apache License, Version 2.0 (the "License"); you may 
#* not use this file except in compliance with the License.  
#* You may obtain a copy of the License at:
#*
#*   http://www.apache.org/licenses/LICENSE-2.0
#*
#* Unless required by applicable law or agreed to in writing, software 
#* distributed under the License is distributed on an "AS IS" BASIS, 
#* WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  
#* See the License for the specific language governing permissions and 
#* limitations under the License.
#*
#* Created on:
#*     Author: 
#*
#****************************************************************************

from ..model.covergroup_model import CovergroupModel
from ..model.coverpoint_model import CoverpointModel
from ..model.coverpoint_cross_model import CoverpointCrossModel

class CovergroupCallbackBase(object):

    def __init__(self):
        self._hit_m = {}
        self._cb = None

    def set_cb(self, cb):
        self._cb = cb

    def sample_cb(self, *args, **kwargs):
        # Call the 'real' sample method
        self.sample(*args, **kwargs)

        self.call_callbacks()

    def call_callbacks(self):
        model : CovergroupModel = self.get_model()
        for cp in model.coverpoint_l:
            self.process_coverpoint(cp)
        for cr in model.cross_l:
            self.process_cross(cr)

    def process_coverpoint(self, cp : CoverpointModel):
        for bi in range(cp.get_n_bins()):
            name = cp.name + "." + cp.get_bin_name(bi)
            if name not in self._hit_m.keys():
                self._hit_m[name] = 0
            hits = cp.get_bin_hits(bi)
            if self._hit_m[name] != hits:
                self._hit_m[name] = hits
                self._cb(name, hits)

    def process_cross(self, cp : CoverpointCrossModel):
        for bi in range(cp.get_n_bins()):
            name = cp.name + "." + cp.get_bin_name(bi)
            if name not in self._hit_m.keys():
                self._hit_m[name] = 0
            hits = cp.get_bin_hits(bi)
            if self._hit_m[name] != hits:
                self._hit_m[name] = hits
                self._cb(name, hits)


            