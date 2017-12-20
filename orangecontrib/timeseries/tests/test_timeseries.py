import unittest

from Orange.data import Table

from orangecontrib.timeseries import Timeseries


class TestTimeseries(unittest.TestCase):
    def test_create_time_variable(self):
        table = Table("iris")
        time_series = Timeseries(table)
        id_1 = id(time_series.attributes)
        time_series.time_variable = time_series.domain.attributes[0]
        self.assertNotEqual(id_1, id(time_series.attributes))
