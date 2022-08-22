import unittest

from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owperiodogram import OWPeriodogram

# There are not many tests here.
# Widget adds just a little to PeriodBase, which is tested within
# tests for OWCorrelogram


class TestPeriodogramWidget(WidgetTest):
    def setUp(self):
        self.widget: OWPeriodogram = self.create_widget(OWPeriodogram)

    def test_does_something_and_doesnt_crash(self):
        ts = Timeseries.from_file("airpassengers")
        self.send_signal(self.widget.Inputs.time_series, ts)

        ts = Timeseries.from_url(
            "http://datasets.biolab.si/core/slovenia-traffic-accidents-2016-events.tab")
        self.send_signal(self.widget.Inputs.time_series, ts)

        ts = Timeseries.from_file("iris")
        self.send_signal(self.widget.Inputs.time_series, ts)


if __name__ == "__main__":
    unittest.main()
