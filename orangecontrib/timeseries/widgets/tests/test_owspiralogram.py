import unittest

from Orange.data import Table
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owspiralogram import OWSpiralogram


class TestOWSpiralogram(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWSpiralogram)  # type: OWSpiralogram

    def test_new_data(self):
        """
        Widget crashes when it gets new data with different domain.
        GH-50
        """
        w = self.widget
        time_series = Timeseries("airpassengers")
        table = Table("iris")
        self.send_signal(w.Inputs.time_series, time_series)
        self.send_signal(w.Inputs.time_series, table)


if __name__ == "__main__":
    unittest.main()