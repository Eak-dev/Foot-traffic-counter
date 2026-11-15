"""Synthetic value-codec security and exact container regressions."""
from collections import OrderedDict, deque
import json
import math
import unittest
from unittest.mock import patch

from tools.ft_state_codec import encode_tree, decode_tree, StateError


class CodecTests(unittest.TestCase):
    def test_roundtrip_retains_integer_keys_tuple_deque_and_order(self):
        value = {1: OrderedDict([(7,deque([(1.2,(.1,.2),(.0,.0,.3,.4))],maxlen=96)),
                                 ('7',deque([(2.,None,-math.inf)],maxlen=96))]), '1':[True,False,None]}
        restored=decode_tree(json.loads(json.dumps(encode_tree(value),allow_nan=False)))
        self.assertEqual(value,restored)
        self.assertIs(type(restored[1]),OrderedDict)
        self.assertIs(type(restored[1][7][0]),tuple)
        self.assertEqual(restored[1][7].maxlen,96)
        self.assertEqual(list(restored),[1,'1'])

    def test_no_arbitrary_objects_or_nonfinite_values(self):
        for bad in (object(),{True:1},float('nan'),float('inf'),2**64):
            with self.assertRaises(StateError):encode_tree(bad)
        for bad in (['__reduce__','module.Class'],['array','object',[], ''],['dict',[[1,2],[1,3]]],
                    ['deque',True,[]],['ninf','extra'],['tuple',{}],{'free':'object'}):
            with self.assertRaises(StateError):decode_tree(bad)

    def test_depth_and_node_budgets(self):
        value=1
        for _ in range(30):value=[value]
        with self.assertRaises(StateError):encode_tree(value)
        with patch('tools.ft_state_codec.MAX_NODES',3),self.assertRaises(StateError):encode_tree([1,2,3])


if __name__=='__main__':unittest.main()
