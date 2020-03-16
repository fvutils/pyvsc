'''
Created on Mar 10, 2020

@author: ballance
'''
from enum import Enum, auto
from pyucis import UCIS_HISTORYNODE_TEST, UCIS_OTHER, UCIS_DU_MODULE, \
    UCIS_ENABLED_STMT, UCIS_ENABLED_BRANCH, UCIS_ENABLED_COND, UCIS_ENABLED_EXPR, \
    UCIS_ENABLED_FSM, UCIS_ENABLED_TOGGLE, UCIS_INST_ONCE, UCIS_SCOPE_UNDER_DU, \
    UCIS_INSTANCE
from pyucis.file_handle import FileHandle
from pyucis.scope import Scope
from pyucis.test_data import TestData
from pyucis.ucis import UCIS
from typing import Dict, List, Set

from vsc.model.covergroup_model import CovergroupModel
from vsc.model.coverpoint_bin_array_model import CoverpointBinArrayModel
from vsc.model.coverpoint_bin_collection_model import CoverpointBinCollectionModel
from vsc.model.coverpoint_model import CoverpointModel
from vsc.model.model_visitor import ModelVisitor
import os
from builtins import set


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
        self.cg_default_du_name = "du"
        self.cg_default_inst_name = "cg_inst"
        self.logicalname = "logicalName"
        self.in_bin_collection = False
        self.active_scope_s = []
        self.cg_name_s : Set[str] = set()

        
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
        print("-- visit_covergroup")
        cg_inst = self.get_cg_inst(cg)
        
        cg_name = cg.name if cg.name is not None else "foobar"
        inst_location = None

        if cg.type_cg is None:
            self.active_scope_s.append(cg_inst.createCovergroup(
                cg_name,
                inst_location,
                1, # weight
                UCIS_OTHER)) # Source type
        else:
            self.active_scope_s.append(cg_inst.createCoverInstance(
                self.get_cg_instname(cg),
                inst_location,
                1, # weight
                UCIS_OTHER)) # Source type
        
        super().visit_covergroup(cg)
        self.active_scope_s.pop()
        
    def visit_coverpoint(self, cp : CoverpointModel):
        active_s = self.active_scope_s[-1]

        cp_name = cp.name
        decl_location = None
        self.active_scope_s.append(active_s.createCoverpoint(
            cp_name,
            decl_location,
            1, # weight
            UCIS_OTHER)) # Source type

        super().visit_coverpoint(cp)
        self.active_scope_s.pop()
        
    def visit_coverpoint_bin_collection(self, bn:CoverpointBinCollectionModel):
        self.in_bin_collection = True
        super().visit_coverpoint_bin_collection(bn)
        self.in_bin_collection = False
        
    def visit_coverpoint_bin_array(self, bn:CoverpointBinArrayModel):
        print("visit_coverpoint_bin_array")
        active_cp = self.active_scope_s[-1]
        decl_location = None
        for i in range((bn.high-bn.low)+1):
            v = bn.low+i
            bn_name = bn.name + "[%d]" % (v,)
            cp_bin = active_cp.createBin(
                bn_name,
                decl_location,
                1, # weight
                bn.get_hits(i),
                bn.name
            )
            
    def get_cg_instname(self, cg : CovergroupModel)->str:
        iname = None
        
        if cg.instname is not None:
            iname = cg.instname
        else:
            iname = cg.name

        for i in range(1000):
            if i == 0:
                if not iname in self.cg_name_s:
                    self.cg_name_s.add(iname)
                    break
            else:
                if not "%s_%d" % (iname,i) in self.cg_name_s:
                    iname = "%s_%d" % (iname,i)
                    self.cg_name_s.add(iname)
                    break

        return iname
        
    def get_cg_inst(self, cg : CovergroupModel) -> Scope:
        if len(self.active_scope_s) > 0:
            return self.active_scope_s[-1]
        else:
            print("-- Create Scope")
            # Need to create a default scope
            from pyucis.source_info import SourceInfo
            file = self.db.createFileHandle("dummy", os.getcwd())
            du_src_info = SourceInfo(file, 0, 0)
            
            cg_default_du = self.db.createScope(
                self.cg_default_du_name,
                du_src_info,
                1, # weight
                UCIS_OTHER, # source language
                UCIS_DU_MODULE,
                UCIS_ENABLED_STMT | UCIS_ENABLED_BRANCH
                | UCIS_ENABLED_COND | UCIS_ENABLED_EXPR
                | UCIS_ENABLED_FSM | UCIS_ENABLED_TOGGLE
                | UCIS_INST_ONCE | UCIS_SCOPE_UNDER_DU)
            
            cg_default_inst = self.db.createInstance(
                self.cg_default_inst_name,
                None, # sourceinfo
                1, # weight
                UCIS_OTHER, # source language
                UCIS_INSTANCE,
                cg_default_du,
                UCIS_INST_ONCE)

            self.active_scope_s.append(cg_default_inst)
            
            return cg_default_inst

    