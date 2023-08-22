'''
Created on May 3, 2021

@author: mballance
'''
from vsc_test_case import VscTestCase

import vsc

class TestRandszArray(VscTestCase):
    
    def test_elems_match_size(self):
        
        @vsc.randobj
        class cls(object):
            
            def __init__(self):
                self.l = vsc.randsz_list_t(vsc.uint16_t())
                
            @vsc.constraint
            def size_c(self):
                self.l.size.inside(vsc.rangelist(0,1,2,4,8,16))
                
            @vsc.constraint
            def val_c(self):
                with vsc.foreach(self.l, idx=True) as idx:
                    self.l[idx] == idx
                
        c = cls()
        
        with c.randomize_with() as it:
            it.l.size > 0
        self.assertIn(c.l.size, [1,2,4,8,16])

        print("size: %d" % c.l.size)        
        for i in range(c.l.size):
            self.assertEqual(c.l[i], i)

    def test_obj_array(self):
        @vsc.randobj
        class MyRandObject:
            def __init__(self):
                self.a =vsc.rand_bit_t(4)

        @vsc.randobj
        class TopRandObj:
            def __init__(self):
                self.a = vsc.randsz_list_t(MyRandObject())
                
                for i in range(5):
                    self.a.append(MyRandObject())

            @vsc.constraint
            def a_c(self):
                self.a.size < 5
                self.a.size > 1

        my_top_rand = TopRandObj()
        my_top_rand.randomize(solve_fail_debug=1)
        self.assertGreater(my_top_rand.a.size, 1)
        self.assertLess(my_top_rand.a.size, 5)
        print("Size: %d" % my_top_rand.a.size)

    def test_arr_sum(self):

        @vsc.randobj
        class ThreadGroupConstraintItem(object):
            def __init__(self, aThreadNum, aSharePercent):
                self.mThreadNum = aThreadNum
                self.mSharePercent = aSharePercent

                self.mSharePercentGoal = self.mSharePercent
                self.mSharePercentDelta = 10
                self.mSharePercentGoalMin = 0
                self.mSharePercentGoalMax = 0
                self._genSharePrecent()
                self.mSharePercentGoalMinConstr =  vsc.rand_uint16_t(0)
                self.mSharePercentGoalMaxConstr =  vsc.rand_uint16_t(0)
                self.mGroupSize = vsc.rand_uint16_t(0)
                self.GroupList = vsc.randsz_list_t(vsc.rand_uint16_t())
                self.GroupListScore = vsc.randsz_list_t(vsc.rand_uint16_t())
        
            @vsc.constraint
            def basic_c(self):
                self.mGroupSize < self.mThreadNum
                self.mGroupSize > 0
                self.GroupList.size == self.mGroupSize
                self.GroupListScore.size == self.mGroupSize
                # self.GroupListSum == self.GroupList.sum
                # self.GroupList.sum == self.GroupListSum 
                # self.GroupListSum == self.mThreadNum
                with vsc.foreach(self.GroupList, idx=True, it=False) as idx:
                    self.GroupList[idx]<= self.mThreadNum
                    self.GroupList[idx]>0
                with vsc.foreach(self.GroupList, idx=True, it=False) as idx:
                    with vsc.if_then(self.GroupList[idx] > 1):
                        self.GroupListScore[idx] == 1
                    with vsc.else_then():
                        self.GroupListScore[idx] == 0
                self.GroupList.sum == self.mThreadNum
                # self.mSharePercentGoalMinConstr == self.mSharePercentGoalMin
                # self.mSharePercentGoalMaxConstr == self.mSharePercentGoalMax
                # self.GroupListScore.sum/self.mGroupSize < int(self.mSharePercentGoalMax/100)
                # self.GroupListScore.sum/self.mGroupSize > int(self.mSharePercentGoalMin/100)

            def _genSharePrecent(self):
                """generate share percent min/max
                """
                if self.mSharePercent > self.mSharePercentDelta:
                    self.mSharePercentMin = self.mSharePercent - self.mSharePercentDelta
                else:
                    self.mSharePercentMin = 0

                if self.mSharePercent < 100 - self.mSharePercentDelta:
                    self.mSharePercentMax = self.mSharePercent + self.mSharePercentDelta
                else:
                    self.mSharePercentMax = 100
        
        my_obj_rand = ThreadGroupConstraintItem(8, 80)
        for i in range(10):
            print("Iter %d", i)
            my_obj_rand.randomize(debug=False)
            self.assertEqual(my_obj_rand.mThreadNum, sum(my_obj_rand.GroupList))
#            with vsc.randomize_with(my_obj_rand):
#                my_obj_rand.GroupList.sum == my_obj_rand.mThreadNum
            print("Thread_num: %0d, GroupList.sum: %d" % (my_obj_rand.mThreadNum, sum(my_obj_rand.GroupList)))
            for i,it in enumerate(my_obj_rand.GroupList):
                print("  GroupList[%d]: %d" % (i, it))
                print("  GroupListScore[%d]: %d" % (i, my_obj_rand.GroupListScore[i]))

