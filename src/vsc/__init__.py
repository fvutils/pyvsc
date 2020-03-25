
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




from vsc.rand_obj import *
from vsc.types import *
from vsc.attrs import *
from vsc.methods import *
from vsc.constraints import *
from vsc.coverage import *
from typing import List
import sys
from vsc.report.coverage_report_visitor import CoverageReportVisitor
from vsc.report.report_text_formatter import ReportTextFormatter


def get_coverage_report(*args, details=False)->str:
    covergroups = None
    
    if len(args) == 0:
        covergroups = CoverageRegistry.inst().covergroup_types()
    else:
        covergroups = [cg.get_model() for cg in args]
        
    v = CoverageReportVisitor(covergroups, details)
    
    return ReportTextFormatter.format(v.report(), False)

def get_coverage_report_model(*args, details=False)->str:
    covergroups = None
    
    if len(args) == 0:
        covergroups = CoverageRegistry.inst().covergroup_types()
    else:
        covergroups = [cg.get_model() for cg in args]
        
    v = CoverageReportVisitor(covergroups, details)
    return v.report()

def report_coverage(*args):
    sys.stdout.write(get_coverage_report(*args))

        