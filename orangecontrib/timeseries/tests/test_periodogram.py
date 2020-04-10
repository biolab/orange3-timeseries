import unittest
import numpy as np

from orangecontrib.timeseries import Timeseries, periodogram, periodogram_nonequispaced


data = Timeseries.from_file('airpassengers')


class TestPeriodogram(unittest.TestCase):
    def test_periodogram(self):
        periods, pgram = periodogram(data.Y)
        self.assertEqual(max(pgram), 1)
        self.assertEqual(np.round(periods[pgram == 1]), 6)

    def test_periodogram_nonequispaced(self):
        periods, pgram = periodogram_nonequispaced(data.X.ravel(), data.Y, detrend='diff')
        self.assertEqual(max(pgram), 1)
