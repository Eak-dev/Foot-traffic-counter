import math
import unittest
from tools.ft_perf_metrics import summarize_resource


class ResourceTests(unittest.TestCase):
    def test_multithread_cpu_and_darwin_memory_units(self):
        r = summarize_resource(10, 25, 5, 128 * 1024**2, 8)
        self.assertEqual(r['cpu_core_seconds'], 30)
        self.assertEqual(r['average_cpu_percent'], 300)
        self.assertEqual(r['logical_capacity_fraction'], .375)
        self.assertEqual(r['peak_worker_mib'], 128)
        self.assertEqual(r['gpu_energy_temperature'], 'NOT_MEASURED')

    def test_zero_cpu_memory_are_valid_not_unmeasured_energy(self):
        r = summarize_resource(1, 0, 0, 0, 1)
        self.assertEqual(r['average_cpu_percent'], 0)
        self.assertEqual(r['gpu_energy_temperature'], 'NOT_MEASURED')

    def test_invalid_clock_cpus_and_nonfinite_samples(self):
        for index in range(5):
            for value in (True, -1, math.nan, math.inf, '1'):
                args = [10, 1, 1, 1024, 8]
                args[index] = value
                with self.assertRaises(ValueError):
                    summarize_resource(*args)
        with self.assertRaises(ValueError):
            summarize_resource(0, 1, 1, 1, 1)
        with self.assertRaises(ValueError):
            summarize_resource(1, 1, 1, 1, 0)
