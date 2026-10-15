import unittest
from tools.ft_zone_entries import ZoneEntryCounter
from tools.ft_count import ValidationError

class EntryTests(unittest.TestCase):
    def counter(self):return ZoneEntryCounter([[.2,.2],[.8,.2],[.8,.8],[.2,.8]],.02)
    def feed(self,c,points,start=0,tid=1):
        for i,p in enumerate(points):c.update(tid,p,start+i*.2)
    def test_entry_and_independent_second_visit(self):
        c=self.counter();self.feed(c,[(.1,.5)]*3+[(.4,.5)]*3)
        self.assertEqual(c.count,1)
        self.feed(c,[(.1,.5)]*3+[(.4,.5)]*3,start=3)
        self.assertEqual(c.count,2)
    def test_initial_occupancy_stationary_exit_not_entries(self):
        c=self.counter();self.feed(c,[(.4,.5)]*6+[(.1,.5)]*6)
        self.assertEqual(c.count,0)
    def test_boundary_jitter_not_entry(self):
        c=self.counter();self.feed(c,[(.1,.5)]*3+[(.19,.5),(.21,.5)]*10)
        self.assertEqual(c.count,0)
    def test_gap_and_new_id_do_not_invent_entry(self):
        c=self.counter();self.feed(c,[(.1,.5)]*3)
        self.feed(c,[(.4,.5)]*3,start=4)
        self.feed(c,[(.4,.5)]*3,start=6,tid=2)
        self.assertEqual(c.count,0)
    def test_entry_from_any_edge(self):
        for out,inside in [((.1,.5),(.4,.5)),((.9,.5),(.6,.5)),((.5,.1),(.5,.4)),((.5,.9),(.5,.6))]:
            c=self.counter();self.feed(c,[out]*3+[inside]*3);self.assertEqual(c.count,1)
    def test_transient_single_inside_detection_not_entry(self):
        c=self.counter();self.feed(c,[(.1,.5)]*3+[(.4,.5),(.1,.5)]*4);self.assertEqual(c.count,0)
    def test_invalid_geometry_and_times(self):
        with self.assertRaises(ValidationError):ZoneEntryCounter([[0,0]]*3)
        c=self.counter();c.update(1,(.5,.5),0)
        with self.assertRaises(ValidationError):c.update(1,(.5,.5),0)
