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

from _io import StringIO
from ctypes import cdll, c_void_p, CFUNCTYPE
from datetime import datetime
import sys
from typing import List

from ucis import UCIS_TESTSTATUS_OK, db
import ucis
from ucis.lib.LibFactory import LibFactory
from ucis.lib.lib_ucis import LibUCIS
from ucis.mem.mem_factory import MemFactory
from ucis.report.coverage_report import CoverageReport
from ucis.report.coverage_report_builder import CoverageReportBuilder
from ucis.report.text_coverage_report_formatter import TextCoverageReportFormatter
from ucis.test_data import TestData
from ucis.ucis import UCIS
from ucis.xml.xml_factory import XmlFactory
from vsc.attrs import *
from vsc.constraints import *
from vsc.coverage import *
from vsc.methods import *
from vsc.rand_obj import *
from vsc.types import *
from vsc.visitors.coverage_save_visitor import CoverageSaveVisitor
from vsc import profile
from vsc.impl.ctor import glbl_debug, glbl_solvefail_debug

from vsc import util


def get_coverage_report(details=False)->str:
    """
    Returns a textual coverage report of all covergroups
    
    :param bool details: Write details, such as the hits in each bin (False)
    :return: String containin coverage report text
    """
    model = get_coverage_report_model()

    out = StringIO()    
    formatter = TextCoverageReportFormatter(model, out)
    formatter.details = details
    formatter.report()
    
    return out.getvalue()

def get_coverage_report_model()->CoverageReport:
    """
    Returns a coverage report model of all covergroups
    
    :return: Object describing collected coverage
    """
    covergroups = CoverageRegistry.inst().covergroup_types()

    db = MemFactory.create()        
    save_visitor = CoverageSaveVisitor(db)
    now = datetime.now
    save_visitor.save(TestData(
        UCIS_TESTSTATUS_OK,
        "UCIS:simulator",
        ucis.ucis_Time()), covergroups)

    return CoverageReportBuilder.build(db)    

def report_coverage(fp=None, details=False):
    """
    Writes a coverage report to a stream (stdout by default)
    
    :param fp: Stream to which to write the report
    :param bool details: Write details, such as the hits in each bin (False)
    """
    if fp is None:
        fp = sys.stdout
    fp.write(get_coverage_report(details))
    
def write_coverage_db(
        filename, 
        fmt="xml",
        libucis=None):
    """
    Writes coverage data to persistent storage using the PyUCIS library.
    
    :param str filename: Destination for coverage data
    :param str fmt: Format of the coverage data. 'xml' and 'libucis' supported
    :param str libucis: Path to a library implementing the UCIS C API (default=None)
    """
    
    formats = ["xml", "libucis"]
    covergroups = CoverageRegistry.inst().covergroup_types()
    db : UCIS
    
    if fmt == "xml" or fmt == "mem":
        db = MemFactory.create()
    elif fmt == "libucis":
        if libucis is not None:
            LibFactory.load_ucis_library(libucis)
        db = LibFactory.create(None)
    else:
        raise Exception("Unsupported coverage-report format " + format 
                        + ". Supported formats: " + str(formats))
        
    save_visitor = CoverageSaveVisitor(db)
    now = datetime.now
    save_visitor.save(TestData(
        UCIS_TESTSTATUS_OK,
        "UCIS:simulator",
        ucis.ucis_Time()), covergroups)
    
    if fmt == "xml":
        XmlFactory.write(db, filename)
    elif fmt != "mem":
        db.write(filename)

    return db

def vsc_debug(val):
    global glbl_debug
    glbl_debug = val
    
def vsc_solvefail_debug(val):
    global glbl_solvefail_debug
    glbl_solvefail_debug = val

    
