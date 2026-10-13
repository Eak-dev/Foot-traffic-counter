"""Offline source-contract tests; never touch a real device or session."""
import copy
import unittest
from unittest.mock import patch
from tools import ft_sd_probe as s


class FixedMetadataTests(unittest.TestCase):
    def setUp(self):
        self.day, self.end = s._day_bounds_utc(s.FIXED_DATE,'+07:00')
        self.row={'startTime':self.day+100,'endTime':self.day+130,'vedio_type':'2',
                  'chn_times':{'1':{'event_start_time':self.day+102},'2':{'event_start_time':self.day+100}}}
    def wrap(self,row):
        return {'playback':{'search_video_results':[{'synthetic':row}]}}
    def test_exact_bounded_request(self):
        req=s._clip_utc_requests(s.FIXED_DATE,7)
        s._validate_requests(req,'clip-utc',s.FIXED_DATE,7)
        utility=req[0]['params']['playback']['search_video_with_utc']
        self.assertEqual(utility,{'channel':0,'id':7,'start_index':0,'end_index':19,'start_time':self.day,'end_time':self.end-1})
        for key,value in [('end_index',999999),('channel',1),('start_time',self.day-1),('extra',True)]:
            bad=copy.deepcopy(req);bad[0]['params']['playback']['search_video_with_utc'][key]=value
            with self.assertRaises(s.SdError):s._validate_requests(bad,'clip-utc',s.FIXED_DATE,7)
        with self.assertRaises(s.SdError):s._validate_requests(req,'clip-utc',s.FIXED_DATE,True)
    def test_fixed_candidate_uses_lens_start(self):
        candidates,count,missing=s._fixed_intervals(self.wrap(self.row))
        self.assertEqual(candidates,[(self.day+102,self.day+130)])
        self.assertEqual((count,missing),(1,0))
    def test_pt_only_and_unlabelled_not_fixed(self):
        self.row['chn_times'].pop('1')
        self.assertEqual(s._fixed_intervals(self.wrap(self.row))[0],[])
        self.row.pop('chn_times')
        self.assertEqual(s._fixed_intervals(self.wrap(self.row)),([],1,1))
    def test_malformed_fields_fail_closed(self):
        for key,val in [('startTime',True),('endTime',self.end+1),('vedio_type',False),('chn_times',{'3':{'event_start_time':self.day+100}}),('chn_times',{'1':{'event_start_time':self.day-1}})]:
            row=copy.deepcopy(self.row);row[key]=val
            with self.subTest(key=key),self.assertRaises(s.SdError):s._fixed_intervals(self.wrap(row))
    def test_duplicate_and_excess_rows(self):
        result=self.wrap(self.row)
        result['playback']['search_video_results']*=2
        with self.assertRaises(s.SdError):s._fixed_intervals(result)
        result['playback']['search_video_results']*=11
        with self.assertRaises(s.SdError):s._fixed_intervals(result)
    def test_bad_target_no_network(self):
        with patch.object(s,'_device_request') as request:
            report=s.probe_fixed_metadata('synthetic','uuid',{})
            self.assertEqual(report['status'],'BLOCKED')
            request.assert_not_called()
