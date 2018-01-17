import unittest

from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owlinechart import OWLineChart


class TestOWLineChart(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWLineChart)  # type: OWLineChart

    def test_no_time_series(self):
        """
        Clean variables list view when no data.
        GH-46
        """
        w = self.widget
        time_series = Timeseries("airpassengers")
        self.send_signal(w.Inputs.time_series, time_series)
        self.send_signal(w.Inputs.time_series, None)
        self.send_signal(w.Inputs.forecast, time_series, 1)
        w.configs[0].view.selectAll()
        w.configs[0].selection_changed()


if __name__ == "__main__":
    unittest.main()
