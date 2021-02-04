from datetime import datetime, timezone
from itertools import product
import unittest
import platform
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

    def test_make_timeseries_from_continuous_var(self):
        table = Table.from_url("http://file.biolab.si/datasets/slovenian-national-assembly-eng.tab")
        time_series = Timeseries.make_timeseries_from_continuous_var(table,
                                                                     'date of birth')
        self.assertEqual(time_series.time_variable.name, 'date of birth')
        self.assertTrue(time_series.time_variable in time_series.domain.metas)

    def test_time_var_removed(self):
        ts_with_tv = Timeseries.from_file('airpassengers')
        # select columns without time variable
        ts_without_tv = Timeseries.from_data_table(ts_with_tv[:,
                                      ts_with_tv.domain.class_var])
        self.assertTrue(ts_with_tv.time_variable)
        # make sure the Timeseries without time variable in domain has
        # time_variable set to None
        self.assertIsNone(ts_without_tv.time_variable)


class TestTimestamp(unittest.TestCase):
    @unittest.skipIf(
        platform.system() == "Windows",
        "On windows date.timestamp() raises OverflowError"
    )
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

    def test_timestamp_windows(self):
        """
        Since test_timestamp cannot be run on Win it is its truncated version
        with hardcoded correct timestamps. It can be only tested with UTC
        since otherwise timestamp would be machine local time dependent
        """
        class T(datetime):
            def timestamp(self):
                nonlocal was_hit
                was_hit = True
                raise OverflowError

        # test different years since 1900 was not a leap year, 2000 was
        # test different timezones to account for naive and aware datetime
        years = [1890, 1991, 2004]
        timestamps = [-2514083978.999995, 673125621.000005, 1083439221.000005]
        for y, y_true in zip(years, timestamps):
            was_hit = False
            test_date = T(y, 5, 1, 19, 20, 21, 5, tzinfo=timezone.utc)

            self.assertEqual(y_true, timestamp(test_date))
            self.assertTrue(was_hit)

    def test_fromtimestamp(self):
        TS = -1234567890
        expected = datetime(1930, 11, 18, 0, 28, 30, tzinfo=timezone.utc)

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
            self.assertEqual(fromtimestamp(TS, tz=timezone.utc), expected)
            self.assertTrue(was_hit)


if __name__ == "__main__":
    unittest.main()
