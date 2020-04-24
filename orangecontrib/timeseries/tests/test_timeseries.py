from datetime import datetime, timezone
from itertools import product
import unittest
from unittest.mock import patch

from Orange.data import Table

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.functions import timestamp, fromtimestamp


class TestTimeseries(unittest.TestCase):
    def test_create_time_variable(self):
        table = Table("iris")
        time_series = Timeseries.from_data_table(table)
        id_1 = id(time_series.attributes)
        time_series.time_variable = time_series.domain.attributes[0]
        self.assertNotEqual(id_1, id(time_series.attributes))


class TestTimestamp(unittest.TestCase):
    def test_timestamp(self):
        local = datetime.now().astimezone().tzinfo

        class T(datetime):
            def timestamp(self):
                nonlocal was_hit
                was_hit = True
                raise OverflowError

        # test different years since 1900 was not a leap year, 2000 was
        # test different timezones to account for naive and aware datetime
        for y, tz in product([1890, 1991, 2004], [None, timezone.utc, local]):
            was_hit = False
            date = datetime(y, 5, 1, 19, 20, 21, 5, tzinfo=tz)
            test_date = T(y, 5, 1, 19, 20, 21, 5, tzinfo=tz)

            self.assertEqual(date.timestamp(), timestamp(test_date))
            self.assertTrue(was_hit)

    def test_fromtimestamp(self):
        TS = -1234567890
        expected = datetime.fromtimestamp(TS)

        was_hit = False

        class MockDatetime(datetime):
            @classmethod
            def fromtimestamp(cls, *args, **kwargs):
                nonlocal was_hit
                if was_hit:
                    return super().fromtimestamp(*args, **kwargs)
                was_hit = True
                raise OSError

        with patch('datetime.datetime', MockDatetime):
            self.assertEqual(fromtimestamp(TS), expected)
            self.assertTrue(was_hit)
