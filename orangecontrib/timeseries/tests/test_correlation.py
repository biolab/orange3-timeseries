import unittest
import numpy as np

from orangecontrib.timeseries import Timeseries, autocorrelation, partial_autocorrelation


data = Timeseries.from_file('airpassengers')


class TestAutocorrelation(unittest.TestCase):
    def test_acf(self):
        acf = autocorrelation(data.Y)
        np.testing.assert_equal(acf[:4, 0], [12, 24, 36, 48])
        np.testing.assert_equal(acf[:4, 1] > 0, True)

    def test_pacf(self):
        pacf = partial_autocorrelation(data.Y)
        np.testing.assert_equal(pacf[:3, 0], [9, 13, 25])
        np.testing.assert_equal(pacf[0, 1] > 0, True)
