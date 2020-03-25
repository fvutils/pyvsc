'''
Created on Mar 24, 2020

@author: ballance
'''
from typing import List

from vsc.model.covergroup_model import CovergroupModel
from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.model_visitor import ModelVisitor
from vsc.report.coverage_report import CoverageReport


class CoverageReportVisitor(ModelVisitor):
    
    def __init__(self,
                 covergroups : List[CovergroupModel],
                 details : bool = False):
        self._covergroups = covergroups
        self._details = details
        self._parent = []
        self._report = None
        
        
    def report(self)->CoverageReport:
        
        self._report = CoverageReport()
        self._parent = [self._report]
        
        for cg in self._covergroups:
            cg.accept(self)
            
        return self._report
            
    def visit_covergroup(self, cg:CovergroupModel):
        cg_r = CoverageReport.Covergroup(cg.name, cg.type_cg is None)
        cg_r.coverage = cg.get_coverage()

        self._parent[-1].covergroups.append(cg_r)
        self._parent.append(cg_r)        
        
        # First, add bin information
        for cp in cg.coverpoint_l:
            cp.accept(self)
            
        for cr in cg.cross_l:
            cr.accept(self)
            
        # Now, go for any instance coverage
        for cg_i in cg.cg_inst_l:
            cg_i.accept(self)
            
        self._parent.pop()
        
    def visit_coverpoint(self, cp:CoverpointModel):
        cp_r = CoverageReport.Coverpoint(cp.name)
        self._parent[-1].coverpoints.append(cp_r)
        
        cp_r.coverage = cp.get_coverage()
        
        if self._details:
            # TODO: Collect information about individual bins
            pass
        
    def visit_coverpoint_cross(self, cp):
        cp_r = CoverageReport.Coverpoint(cp.name)
        self._parent[-1].crosses.append(cp_r)
        
        cp_r.coverage = cp.get_coverage()
        
        if self._details:
            # TODO: Collect information about individual bins
            pass
        
        
#     def report_covergroup_data(self, cg):
#         for cp in cg.coverpoint_l:
#             cp.accept(self)
#             
#         for cr in cg.cross_l:
#             cr.accept(self)
#         
#     def writeln(self, msg, *args):
#         line = self._indent
#         line += msg % args
#         self._report.write(line + "\n")
#     
#     def __enter__(self):
#         self._indent += "    "
#     
#     def __exit__(self, t, v, tb):
#         self._indent = self._indent[:-4]
#         
#     def indent(self):
#         return self
        
#     def visit_coverpoint(self, cp:CoverpointModel):
#         self.writeln("Coverpoint: %s %f", cp.name, cp.get_coverage())
# 
#         with self.indent():
#             for bi in range(cp.get_n_bins()):
#                 self.writeln("%s: %d/%d", cp.get_bin_name(bi), cp.get_n_hit_bins(), cp.get_n_bins())
#             
            

        
        