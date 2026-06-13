'''
Dataclass-front-end parallel of ve/unit/test_if_else.py.

if_then / else_if / else_then in all spellings, plus the enum if/else case
(Phase 2 enums).
'''
from enum import IntEnum

from dc_test_case import DcTestCase
import vsc.dc as vdc


class TestIfElse(DcTestCase):

    def test_if_then(self):

        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()
            d: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):

                with vdc.if_then(self.a == 1):
                    self.b == 1

        v = my_s()
        v.randomize()

        v.a = 1
        v.a = 2

    def test_else_if(self):

        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()
            d: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):

                self.a in vdc.rangelist(1, 5)

                with vdc.if_then(self.a == 1):
                    self.b in vdc.rangelist(0, 10)
                with vdc.else_if(self.a == 2):
                    self.b in vdc.rangelist(11, 20)
                with vdc.else_if(self.a == 3):
                    self.b in vdc.rangelist(21, 30)
                with vdc.else_if(self.a == 4):
                    self.b in vdc.rangelist(31, 40)
                with vdc.else_if(self.a == 5):
                    self.b in vdc.rangelist(41, 50)

        v = my_s()
        for i in range(8):
            v.randomize()

    def test_else_if_2(self):

        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()
            d: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):

                self.a == 5

                with vdc.if_then(self.a == 1):
                    self.b == 1
                with vdc.else_if(self.a == 2):
                    self.b == 2
                with vdc.else_if(self.a == 3):
                    self.b == 4
                with vdc.else_if(self.a == 4):
                    self.b == 8
                with vdc.else_if(self.a == 5):
                    self.b == 16
                with vdc.else_then():
                    self.b == 0

        v = my_s()
        for i in range(8):
            v.randomize()

    def test_else_if_3(self):

        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()
            d: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):

                self.a == 5

                with vdc.if_then(self.a == 1):
                    self.b == 1
                with vdc.else_if(self.a == 2):
                    self.b == 2
                with vdc.else_if(self.a == 3):
                    self.b == 4
                with vdc.else_if(self.a == 4):
                    self.b == 8
                with vdc.else_if(self.a == 5):
                    self.b == 16
                with vdc.else_then:
                    self.b == 0

        v = my_s()
        for i in range(8):
            v.randomize()

    def test_else_then(self):

        @vdc.dataclass
        class my_s(vdc.RandClass):
            a: vdc.u8 = vdc.rand()
            b: vdc.u8 = vdc.rand()
            c: vdc.u8 = vdc.rand()
            d: vdc.u8 = vdc.rand()

            @vdc.constraint
            def ab_c(self):

                self.a == 1

                with vdc.if_then(self.a == 1):
                    self.b == 1
                with vdc.else_then():
                    self.b == 2

        v = my_s()
        vdc.randomize(v)

    def test_enum_if_else(self):

        class CmdTypes(IntEnum):
            TYPE_A = 0
            TYPE_B = 1

        @vdc.dataclass
        class Cmd(vdc.RandClass):
            cmd_type: CmdTypes = vdc.rand()
            cmd_op: vdc.u1 = vdc.rand()

            @vdc.constraint
            def op_type_combination_c(self):
                with vdc.if_then(self.cmd_type == CmdTypes.TYPE_B):
                    self.cmd_op == 1

        cmd = Cmd()
        cmd.randomize()
