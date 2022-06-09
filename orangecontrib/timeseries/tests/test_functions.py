import unittest
from unittest.mock import patch

import numpy as np

from orangecontrib.timeseries.functions import moving_sum, \
    windowed_func, moving_count_nonzero, moving_count_defined, _windowed, \
    windowed_span, _windowed_weighted, windowed_linear_MA, \
    windowed_exponential_MA, windowed_cumsum, windowed_cumprod, windowed_mode, \
    windowed_harmonic_mean


class TestMovingTransform(unittest.TestCase):
    def test_moving_sum(self):
        a = np.array([3, 8, 6, 4, 2, 4, 6, 8, 1, 2, 4])
        np.testing.assert_equal(moving_sum(a, 3),
                                np.array([17, 18, 12, 10, 12, 18, 15, 11,  7]))
        np.testing.assert_equal(moving_sum(a, 7),
                                np.array([33, 38, 31, 27, 27]))
        np.testing.assert_equal(moving_sum(a, 7, 2),
                                np.array([33, 31, 27]))
        np.testing.assert_equal(moving_sum(a, 3, 3),
                                np.array([17, 10, 15]))
        np.testing.assert_equal(moving_sum(a, 3, 4),
                                np.array([17, 12, 7]))
        np.testing.assert_equal(moving_sum(a, 3, 5),
                                np.array([17, 18]))
        np.testing.assert_equal(moving_sum(a, 10, 1),
                                np.array([44, 45]))
        np.testing.assert_equal(moving_sum(a, 10, 5),
                                np.array([44]))
        np.testing.assert_equal(moving_sum(a, 15),
                                np.array([]))
        np.testing.assert_equal(moving_sum(a, 15, 3),
                                np.array([]))

        np.testing.assert_equal(moving_sum(np.array([1, 2, np.nan, 4]), 3),
                                [3, 6])

    def test_count_nonzero(self):
        a = np.array([3, 0, 0, 4, 2, 4, 6, 0, 0, 0, 4])
        np.testing.assert_equal(moving_count_nonzero(a, 3),
                                np.array([1, 1, 2, 3, 3, 2, 1, 0, 1]))
        np.testing.assert_equal(moving_count_nonzero(a, 7),
                                np.array([5, 4, 4, 4, 4]))
        np.testing.assert_equal(moving_count_nonzero(a, 7, 2),
                                np.array([5, 4, 4]))
        np.testing.assert_equal(moving_count_nonzero(a, 3, 3),
                                np.array([1, 3, 1]))
        np.testing.assert_equal(moving_count_nonzero(a, 3, 4),
                                np.array([1, 3, 1]))
        np.testing.assert_equal(moving_count_nonzero(a, 3, 5),
                                np.array([1, 2]))
        np.testing.assert_equal(moving_count_nonzero(a, 10, 1),
                                np.array([5, 5]))
        np.testing.assert_equal(moving_count_nonzero(a, 10, 5),
                                np.array([5]))
        np.testing.assert_equal(moving_count_nonzero(a, 15),
                                np.array([]))
        np.testing.assert_equal(moving_count_nonzero(a, 15, 3),
                                np.array([]))

        np.testing.assert_equal(moving_count_nonzero(np.array([1, 2, np.nan, np.nan, 4]), 3),
                                [2, 1, 1])

    def test_count_defined(self):
        a = np.array([3, np.nan, np.nan, 4, 0, 0, 6, np.nan, np.nan, np.nan, 4])
        np.testing.assert_equal(moving_count_defined(a, 3),
                                np.array([1, 1, 2, 3, 3, 2, 1, 0, 1]))
        np.testing.assert_equal(moving_count_defined(a, 7),
                                np.array([5, 4, 4, 4, 4]))
        np.testing.assert_equal(moving_count_defined(a, 7, 2),
                                np.array([5, 4, 4]))
        np.testing.assert_equal(moving_count_defined(a, 3, 3),
                                np.array([1, 3, 1]))
        np.testing.assert_equal(moving_count_defined(a, 3, 4),
                                np.array([1, 3, 1]))
        np.testing.assert_equal(moving_count_defined(a, 3, 5),
                                np.array([1, 2]))
        np.testing.assert_equal(moving_count_defined(a, 10, 1),
                                np.array([5, 5]))
        np.testing.assert_equal(moving_count_defined(a, 10, 5),
                                np.array([5]))
        np.testing.assert_equal(moving_count_defined(a, 15),
                                np.array([]))
        np.testing.assert_equal(moving_count_defined(a, 15, 3),
                                np.array([]))

    def test_windowed(self):
        a = np.array([3, 8, 6, 4, 2, 4, 6, 8, 1, 2, 4])
        np.testing.assert_equal(_windowed(a[:6], 3, 1),
                                [[3, 8, 6], [8, 6, 4], [6, 4, 2], [4, 2, 4]])

        a = np.array([3, 8, 6, 4, 2, 4, 6, 8, 1, 2, 4])
        np.testing.assert_equal(_windowed(a, 3, 3),
                                [[3, 8, 6], [4, 2, 4], [6, 8, 1]])

        a = np.array([3, 8, 6, 4, 2, 4, 6, 8, 1, 2, 4])
        np.testing.assert_equal(_windowed(a, 3, 5),
                                [[3, 8, 6], [4, 6, 8]])

        a = np.array([3, 8, 6, 4, 2, 4, 6, 8, 1, 2, 4])
        np.testing.assert_equal(_windowed(a, 10, 1),
                                [[3, 8, 6, 4, 2, 4, 6, 8, 1, 2],
                                 [8, 6, 4, 2, 4, 6, 8, 1, 2, 4]])

        a = np.array([3, 8, 6, 4, 2, 4, 6, 8, 1, 2, 4])
        np.testing.assert_equal(_windowed(a, 4, 2),
                                [[3, 8, 6, 4], [6, 4, 2, 4],
                                 [2, 4, 6, 8], [6, 8, 1, 2]])

        a = np.array([3, 8, 6, 4, 2, 4, 6, 8, 1, 2, 4])
        np.testing.assert_equal(_windowed(a, 11, 1),
                                [list(a)])

        a = np.array([3, 8, 6, 4, 2, 4, 6, 8, 1, 2, 4])
        np.testing.assert_equal(_windowed(a, 11, 2),
                                [list(a)])

        a = np.array([3, 8, 6, 4, 2, 4, 6, 8, 1, 2, 4])
        self.assertEqual(len(_windowed(a, 15, 2)), 0)

    def test_windowed_func(self):
        def move_sum(x, width, shift=1):
            return windowed_func(np.sum, x, width, shift)

        a = np.array([3, 8, 6, 4, 2, 4, 6, 8, 1, 2, 4])
        np.testing.assert_equal(move_sum(a, 3),
                                np.array([17, 18, 12, 10, 12, 18, 15, 11,  7]))
        np.testing.assert_equal(move_sum(a, 7),
                                np.array([33, 38, 31, 27, 27]))
        np.testing.assert_equal(move_sum(a, 7, 2),
                                np.array([33, 31, 27]))
        np.testing.assert_equal(move_sum(a, 3, 3),
                                np.array([17, 10, 15]))
        np.testing.assert_equal(move_sum(a, 3, 4),
                                np.array([17, 12, 7]))
        np.testing.assert_equal(move_sum(a, 3, 5),
                                np.array([17, 18]))
        np.testing.assert_equal(move_sum(a, 10, 1),
                                np.array([44, 45]))
        np.testing.assert_equal(move_sum(a, 10, 5),
                                np.array([44]))
        np.testing.assert_equal(move_sum(a, 15),
                                np.array([]))
        np.testing.assert_equal(move_sum(a, 15, 3),
                                np.array([]))

    def test_windowed_span(self):
        a = np.array([3, 8, 6, 4, 2, 4, 6, 8, 1, 2, 4])
        np.testing.assert_equal(windowed_span(a, 3, 1),
                                np.array([5, 4, 4, 2, 4, 4, 7, 7, 3]))

        a = np.array([3, 8, 6, 4, 2, 4, 6, 8, 1, 2, 4])
        np.testing.assert_equal(windowed_span(a, 3, 2),
                                np.array([5, 4, 4, 7, 3]))

        a = np.array([3, 8, np.nan, 4, 2, np.nan, 6, 8])
        np.testing.assert_equal(windowed_span(a, 3, 1),
                                np.array([5, 4, 2, 2, 4, 2]))

    def test_windowed_weighted(self):
        a = np.array([3, 8, 6, 4, 2, 4, 6, 8])
        np.testing.assert_equal(
            _windowed_weighted(a, np.array([1, 0, -2]), 1),
            np.array([3 - 12, 8 - 8, 6 - 4, 4 - 8, 2 - 12, 4 - 16]))

        a = np.array([3, np.nan, 6, 4, np.nan, 4, 6, 8])
        np.testing.assert_equal(
            _windowed_weighted(a, np.array([1, 0, -2]), 1),
            np.array([3 - 12, -4, -6, 4 - 8, -6, 4 - 16]))

    @patch("orangecontrib.timeseries.functions._windowed_weighted")
    def test_windowed_MA(self, ww):
        a = np.array([3, 8, 6, 4, 2, 4, 6, 8])

        windowed_linear_MA(a, 4, 1)
        np.testing.assert_equal(ww.call_args[0][1], np.array([1, 2, 3, 4]) / 10)

        windowed_linear_MA(a, 2, 1)
        np.testing.assert_equal(ww.call_args[0][1], np.array([1, 2]) / 3)

        windowed_exponential_MA(a, 4, 1)
        weights = ww.call_args[0][1]
        factors = weights[1:] / weights[:-1]
        np.testing.assert_almost_equal(factors, factors[0])
        np.testing.assert_almost_equal(np.sum(weights), 1)

        windowed_exponential_MA(a, 6, 1)
        weights = ww.call_args[0][1]
        factors = weights[1:] / weights[:-1]
        np.testing.assert_almost_equal(factors, factors[0])
        np.testing.assert_almost_equal(np.sum(weights), 1)

    def test_windowed_cumsum(self):
        a = np.array([3, 8, 6, 4, np.nan, 4, 6, 8])
        np.testing.assert_equal(windowed_cumsum(a, 3, 1),
                                [17, 21, 21, 25, 31, 39])
        np.testing.assert_equal(windowed_cumsum(a, 3, 2),
                                [17, 21, 31])
        a = np.array([3, 8, 6, 4, 2, 4, 6, 8])
        np.testing.assert_equal(windowed_cumsum(a, 5, 1),
                                [23, 27, 33, 41])

    def test_windowed_cumprod(self):
        a = np.array([3, 8, 6, 4, np.nan, 4, 6, 8])
        np.testing.assert_equal(windowed_cumprod(a, 3, 1),
                                [3 * 8 * 6,
                                 3 * 8 * 6 * 4,
                                 3 * 8 * 6 * 4,
                                 3 * 8 * 6 * 4 * 4,
                                 3 * 8 * 6 * 4 * 4 * 6,
                                 3 * 8 * 6 * 4 * 4 * 6 * 8])

    def test_windowed_cumsum(self):
        a = np.array([3, 3, 2, 2])
        np.testing.assert_equal(windowed_mode(a, 3, 1), [3, 2])
        a = np.array([3, 3, 2, 2, np.nan, 2, np.nan, np.nan, np.nan])
        np.testing.assert_equal(windowed_mode(a, 3, 1),
                                [3, 2, 2, 2, 2, 2, np.nan])

    def test_windowed_harmonic_mean(self):
        a = np.array([3, 3, 2, 2, 2, 0, 0, 0, 1, 2, 3, np.nan, np.nan, np.nan])
        np.testing.assert_almost_equal(
            windowed_harmonic_mean(a, 3, 1),
            [2.5714286, 2.25, 2, 0, 0, 0, 0, 0, 1.63636363, np.nan, np.nan, np.nan])

    def test_windowed_linear_MA(self):
        a = np.array([1, 2, 3, 8, 5])
        np.testing.assert_almost_equal(
            windowed_linear_MA(a, 3, 1),
            [(3 * 3 + 2 * 2 + 1 * 1) / 6,
             (8 * 3 + 3 * 2 + 2 * 1) / 6,
             (5 * 3 + 8 * 2 + 3 * 1) / 6])
        np.testing.assert_almost_equal(
            windowed_linear_MA(a, 5, 1),
            [(5 * 5 + 8 * 4 + 3 * 3 + 2 * 2 + 1 * 1) / (1 + 2 + 3 + 4 + 5)])

        a = np.array([1, 2, 3, np.nan, 5])
        np.testing.assert_almost_equal(
            windowed_linear_MA(a, 3, 1),
            [(3 * 3 + 2 * 2 + 1 * 1) / 6,
             (3 * 2 + 2 * 1) / 3,
             (5 * 3 + 3 * 1) / 4])

        a = np.array([1, np.nan, np.nan, np.nan, 5, 6])
        np.testing.assert_almost_equal(
            windowed_linear_MA(a, 3, 1),
            [1, np.nan, 5, (6 * 3 + 5 * 2) / 5])

    def test_windowed_exponentional_MA(self):
        a = np.array([1, 2, 3, 4, 5])
        np.testing.assert_almost_equal(
            windowed_exponential_MA(a, 3, 1),
            [2.4285714, 3.4285714, 4.4285714])


if __name__ == "__main__":
    unittest.main()
