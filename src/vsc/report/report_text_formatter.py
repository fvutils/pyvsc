'''
Created on Mar 25, 2020

@author: ballance
'''
from vsc.report.coverage_report import CoverageReport
from _io import StringIO

class ReportTextFormatter(object):
    
    def __init__(
            self, 
            report : CoverageReport,
            colorize : bool):
        self._report = report
        self._colorize = colorize
        self._output = StringIO()
        self._ind = ""
        pass
    
    @staticmethod
    def format(
            report : CoverageReport, 
            colorize=False):
        
        formatter = ReportTextFormatter(report, colorize)
        
        return formatter.format_report()
    
    def indent(self):
        return self
    
    def __enter__(self):
        self._ind += "    "
    
    def __exit__(self, t, v, tb):
        self._ind = self._ind[:-4]
        
    def writeln(self, fmt, *args):
        msg = fmt % args
        self._output.write(self._ind + msg + "\n")
    
    def format_report(self):
        for cg in self._report.covergroups:
            self.process_covergroup(cg)
            
        return self._output.getvalue()
            
    def process_covergroup(self, cg : CoverageReport.Covergroup):
        self.writeln("%sCovergroup %s: %f%%", 
                     "Type " if cg.is_type else "Inst ",
                     cg.name, cg.coverage)
        
        with self.indent():
            for cp in cg.coverpoints:
                self.process_coverpoint(cp)
            for cr in cg.crosses:
                self.process_cross(cr)
                
            for cg_i in cg.covergroups:
                self.process_covergroup(cg_i)
                
    def process_coverpoint(self, cp : CoverageReport.Coverpoint):
        self.writeln("Coverpoint %s : %f%%", cp.name, cp.coverage)
        
    def process_cross(self, cr : CoverageReport.Coverpoint):
        self.writeln("Cross %s : %f%%", cr.name, cr.coverage)
        
        
        
    
    