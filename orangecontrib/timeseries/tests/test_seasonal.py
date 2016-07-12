import unittest
import numpy as np

from orangecontrib.timeseries import Timeseries, seasonal_decompose


data = Timeseries('airpassengers')


class TestSeasonalDecompose(unittest.TestCase):
    def test_seasonal_decomposition(self):
        decomp = seasonal_decompose(data[:, data.domain.class_var], model='multiplicative')
        self.assertEqual(len(decomp.domain), 4)

        np.testing.assert_almost_equal(
            decomp[:, 'Air passengers (season. adj.)'],
            decomp[:, 'Air passengers (trend)'].X * decomp[:, 'Air passengers (residual)'].X
        )
        np.testing.assert_almost_equal(
            data[:, data.domain.class_var],
            decomp[:, 'Air passengers (season. adj.)'] * decomp[:, 'Air passengers (seasonal)'].X
        )
