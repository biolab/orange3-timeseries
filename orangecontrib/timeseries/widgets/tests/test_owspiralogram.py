import unittest

from Orange.data import Table
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owspiralogram import OWSpiralogram


class TestOWSpiralogram(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWSpiralogram)  # type: OWSpiralogram

    @staticmethod
    def select_item(widget, index):
        widget.indices = [index]
        widget.commit()

    def test_new_data(self):
        """
        Widget crashes when it gets new data with different domain.
        GH-50
        """
        w = self.widget
        time_series1 = Timeseries.from_file("airpassengers")
        url = "http://file.biolab.si/datasets/cyber-security-breaches.tab"
        time_series2 = Timeseries.from_url(url)
        self.send_signal(w.Inputs.time_series, time_series1)
        self.select_item(w, 0)
        output1 = self.get_output(w.Outputs.time_series)
        self.send_signal(w.Inputs.time_series, time_series2)
        self.select_item(w, 0)
        output2 = self.get_output(w.Outputs.time_series)
        self.assertNotEqual(output1, output2)

    def test_no_datetime(self):
        """ Raise error if no data with TimeVariable """
        w = self.widget
        time_series = Timeseries.from_file("airpassengers")
        table = Table.from_file('iris')
        self.send_signal(w.Inputs.time_series, time_series)
        self.assertFalse(w.Error.no_time_variable.is_shown())
        self.send_signal(w.Inputs.time_series, table)
        self.assertTrue(w.Error.no_time_variable.is_shown())
        self.send_signal(w.Inputs.time_series, time_series)
        self.assertFalse(w.Error.no_time_variable.is_shown())

    def test_tz_aggregation(self):
        """ Aggregation should consider timezone """
        w = self.widget
        data = Timeseries.from_file('airpassengers')[:20]
        self.send_signal(w.Inputs.time_series, data)
        # select the first item
        self.select_item(w, 0)
        output = self.get_output(w.Outputs.time_series)
        self.assertEqual(output[0][0], "1949-01-01")


if __name__ == "__main__":
    unittest.main()
