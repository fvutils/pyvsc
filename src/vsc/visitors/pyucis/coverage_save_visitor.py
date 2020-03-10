'''
Created on Mar 10, 2020

@author: ballance
'''
from _pydecimal import _PyHASH_10INV
from enum import Enum, auto
from pyucis import UCIS_HISTORYNODE_TEST, UCIS_OTHER, UCIS_DU_MODULE, \
    UCIS_ENABLED_STMT, UCIS_ENABLED_BRANCH, UCIS_ENABLED_COND, UCIS_ENABLED_EXPR, \
    UCIS_ENABLED_FSM, UCIS_ENABLED_TOGGLE, UCIS_INST_ONCE, UCIS_SCOPE_UNDER_DU, \
    UCIS_INSTANCE
from pyucis.file_handle import FileHandle
from pyucis.scope import Scope
from pyucis.test_data import TestData
from pyucis.ucis import UCIS
from typing import Dict, List

from vsc.model.covergroup_model import CovergroupModel
from vsc.model.coverpoint_bin_array_model import CoverpointBinArrayModel
from vsc.model.coverpoint_bin_collection_model import CoverpointBinCollectionModel
from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.model_visitor import ModelVisitor
from vsc.model.source_info import SourceInfo
import os


class SavePhase(Enum):
    CollectSources = auto()

class CoverageSaveVisitor(ModelVisitor):
    # Create design units (module types)
    # - 
    # Test data
    # Instance (points to design unit)
    # Create covergroup, relative to the instance hierarchy
    # - Create coverpoints
    #   - Create bins
    
    def __init__(self, db : UCIS):
        self.phase = SavePhase.CollectSources
        self.db = db
        # Map of filename -> FileHandle 
        self.file_m : Dict[str,FileHandle] = {}
        self.cg_default_du = None
        self.cg_default_du_name = "du"
        self.cg_default_inst = None
        self.cg_default_inst_name = "cg_inst"
        self.logicalname = "logicalName"
        self.active_cg = None
        self.active_cp = None
        self.in_bin_collection = False

        
    def save(self, td : TestData, cg_l : List[CovergroupModel]):

        # First, go through all scopes to identify
        # the relevant source files        
        self.phase = SavePhase.CollectSources
        
        # First, create a history node
        histnode = self.db.createHistoryNode(
            None,
            self.logicalname,
            "foo.ucis", # Why do we need to pass this in?
            UCIS_HISTORYNODE_TEST)
        histnode.setTestData(td)
        
        for cg in cg_l:
            cg.accept(self)

    def visit_covergroup(self, cg : CovergroupModel):
        cg_inst = self.get_cg_inst(cg)
        
        cg_name = cg.name if cg.name is not None else "foobar"
        inst_location = None
        
        self.active_cg = cg_inst.createCovergroup(
            cg_name,
            inst_location,
            1, # weight
            UCIS_OTHER) # Source type
        
        super().visit_covergroup(cg)
        self.active_cg = None
        
    def visit_coverpoint(self, cp : CoverpointModel):

        cp_name = cp.name
        decl_location = None
        self.active_cp = self.active_cg.createCoverpoint(
            cp_name,
            decl_location,
            1, # weight
            UCIS_OTHER) # Source type

        super().visit_coverpoint(cp)
        self.active_cp = None
        
    def visit_coverpoint_bin_collection(self, bn:CoverpointBinCollectionModel):
        self.in_bin_collection = True
        super().visit_coverpoint_bin_collection(bn)
        self.in_bin_collection = False
        
    def visit_coverpoint_bin_array(self, bn:CoverpointBinArrayModel):
        print("visit_coverpoint_bin_array")
        decl_location = None
        for i in range((bn.high-bn.low)+1):
            v = bn.low+i
            bn_name = bn.name + "[%d]" % (v,)
            cp_bin = self.active_cp.createBin(
                bn_name,
                decl_location,
                1, # weight
                bn.get_hits(i),
                bn.name
            )
        
    def get_cg_inst(self, cg : CovergroupModel) -> Scope:
        if self.cg_default_du is None:
            from pyucis.source_info import SourceInfo
            file = self.db.createFileHandle("dummy", os.getcwd())
            du_src_info = SourceInfo(file, 0, 0)
            
            self.cg_default_du = self.db.createScope(
                self.cg_default_du_name,
                du_src_info,
                1, # weight
                UCIS_OTHER, # source language
                UCIS_DU_MODULE,
                UCIS_ENABLED_STMT | UCIS_ENABLED_BRANCH
                | UCIS_ENABLED_COND | UCIS_ENABLED_EXPR
                | UCIS_ENABLED_FSM | UCIS_ENABLED_TOGGLE
                | UCIS_INST_ONCE | UCIS_SCOPE_UNDER_DU)
            
        if self.cg_default_inst is None:
            self.cg_default_inst = self.db.createInstance(
                self.cg_default_inst_name,
                None, # sourceinfo
                1, # weight
                UCIS_OTHER, # source language
                UCIS_INSTANCE,
                self.cg_default_du,
                UCIS_INST_ONCE)

        return self.cg_default_inst            
            
    