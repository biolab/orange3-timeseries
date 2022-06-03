import unittest
from unittest.mock import patch

import numpy as np

from Orange.data import ContinuousVariable, Domain, Table
from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.functions import moving_transform, moving_sum, \
    windowed_func

data = Timeseries.from_file('airpassengers')


class TestMovingTransform(unittest.TestCase):
    @unittest.skip("reenable this for Orange 3.33")
    def test_duplicated_names(self):
        def mock_transform(*_, **__):
            return np.zeros(10)

        def mock_from_numpy(domain, *_, **__):
            return [attr.name for attr in domain.attributes][4:]

        domain = Domain([ContinuousVariable(x) for x in "abc"] +
                        [ContinuousVariable("c (2; print)")],
                        ContinuousVariable("t"))
        data = Timeseries.from_numpy(domain, np.zeros((10, 4)), np.arange(10),
                                     time_attr=domain["t"])
        with patch("orangecontrib.timeseries.functions._moving_transform",
                   new=mock_transform), \
                patch("orangecontrib.timeseries.Timeseries.from_numpy",
                      new=mock_from_numpy):
            self.assertEqual(moving_transform(
                data,
                (("a", 2, abs),
                 ("a", 3, len),
                 ("a", 3, len),
                 ("c", 2, print))
            ),
                ["a (2; abs)", "a (3; len) (1)", "a (3; len) (2)",
                 'c (2; print) (1)']
            )

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


if __name__ == "__main__":
    unittest.main()