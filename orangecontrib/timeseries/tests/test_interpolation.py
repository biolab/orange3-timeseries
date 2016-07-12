import unittest
import numpy as np

from orangecontrib.timeseries import Timeseries, interpolate_timeseries


class TestInterpolation(unittest.TestCase):
    def setUp(self):
        data = Timeseries('airpassengers')
        data.Y[:2] = np.nan
        data.Y[10:15] = np.nan
        data.Y[-2:] = np.nan
        self.data = data

    def test_methods(self):
        for method in ('linear', 'cubic', 'nearest', 'mean'):
            interpolated = interpolate_timeseries(self.data, method=method)
            self.assertFalse(np.isnan(interpolated.Y).any())
            self.assertTrue(np.isnan(self.data.Y).any())
