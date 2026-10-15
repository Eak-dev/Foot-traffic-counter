import copy
import unittest
from tools import ft_sd_probe as sd

class NoonWindowTests(unittest.TestCase):
    def test_exact_noon_getter(self):
        r=sd._clip_noon_requests(sd.FIXED_DATE, 42)
        sd._validate_requests(r, 'clip-noon', sd.FIXED_DATE, 42)
        q=r[0]['params']['playback']['search_video_with_utc']
        start,_=sd._day_bounds_utc(sd.FIXED_DATE,'+07:00')
        self.assertEqual((q['start_time']-start,q['end_time']-start),(42900,43499))
        self.assertEqual(q['end_index'],19)
        for field,value in [('start_time',start),('channel',True),('end_index',20)]:
            bad=copy.deepcopy(r)
            bad[0]['params']['playback']['search_video_with_utc'][field]=value
            with self.assertRaises(sd.SdError): sd._validate_requests(bad,'clip-noon',sd.FIXED_DATE,42)

    def test_nearest_noon(self):
        from unittest.mock import patch
        from tools import ft_media_probe as m
        day,_=sd._day_bounds_utc(sd.FIXED_DATE,'+07:00')
        noon=day+43200
        with patch.object(m,'LIST_WINDOW','noon'), patch.object(m,'CLIP_SELECTION','nearest_noon'):
            self.assertEqual(m._select_fixed_interval([(noon-300,noon-280),(noon-100,noon+80),(noon+100,noon+120)]),(noon-100,noon+80))
        with patch.object(m,'LIST_WINDOW','day'), patch.object(m,'CLIP_SELECTION','nearest_noon'):
            with self.assertRaises(m.SampleError): m._select_fixed_interval([(noon,noon+30)])
