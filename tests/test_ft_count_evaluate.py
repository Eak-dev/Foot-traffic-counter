import unittest
from tools.ft_count_evaluate import evaluate

def e(t,d='forward'):return {'time_seconds':t,'direction':d}

class EvaluationTests(unittest.TestCase):
    def test_direction_error_is_not_correct_event(self):
        r=evaluate([e(3),e(8,'backward')],[e(3),e(8)],[0,10])
        self.assertEqual((r['true_positive'],r['false_positive'],r['false_negative']),(1,1,1))
        self.assertEqual(r['aggregate_count_agreement'],1)
        self.assertEqual(r['f1'],.5)
    def test_matching_maximizes_pairs_not_greedy_nearest(self):
        r=evaluate([e(2),e(3)],[e(1),e(2.1)],[0,10],1)
        self.assertEqual(r['true_positive'],2)
    def test_outside_window_and_duplicate_prediction(self):
        r=evaluate([e(2),e(2),e(12)],[e(2)],[0,10])
        self.assertEqual((r['true_positive'],r['false_positive']),(1,1))
    def test_empty_negative(self):
        r=evaluate([],[],[0,10]);self.assertEqual(r['aggregate_count_agreement'],1)
        self.assertIsNone(r['precision'])

    def test_report_binding_rejects_wrong_clip_or_geometry(self):
        from tools.ft_count_evaluate import evaluate_report
        r={'input_sha256':'a'*64,'config_sha256':'b'*64,'events':[e(2)]}
        g={**r,'window_seconds':[0,10]}
        self.assertEqual(evaluate_report(r,g)['true_positive'],1)
        for k in ('input_sha256','config_sha256'):
            with self.assertRaises(ValueError):evaluate_report(r,{**g,k:'c'*64})
