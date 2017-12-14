import unittest

import numpy as np

from Orange.data import Table
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owtabletotimeseries import OWTableToTimeseries


class TestAsTimeSeriesWidget(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWTableToTimeseries)  # type: OWTableToTimeseries

    def test_timeseries_column_nans(self):
        """
        When cannot create Timeseries make sure output is None.
        GH-30
        """
        w = self.widget
        data = Table("iris")[:2]
        self.assertFalse(w.Error.nan_times.is_shown())
        self.send_signal(w.Inputs.data, data)
        self.assertFalse(w.Error.nan_times.is_shown())
        self.assertIsInstance(self.get_output(w.Outputs.time_series), Timeseries)
        data.X[:, 0] = np.nan
        self.send_signal(w.Inputs.data, data)
        self.assertTrue(w.Error.nan_times.is_shown())
        self.assertIsNone(self.get_output(w.Outputs.time_series))


if __name__ == "__main__":
    unittest.main()
