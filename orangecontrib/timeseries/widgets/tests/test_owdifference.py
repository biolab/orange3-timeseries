import unittest

from Orange.widgets.utils.itemmodels import select_rows
from orangewidget.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owdifference import OWDifference


class TestOWAggregate(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWDifference)  # type: OWDifference
        url = "https://datasets.biolab.si/core/ewba-slovenia-illegal-dumpsites.tab"
        self.data = Timeseries.from_url(url)

    def test_saved_selection(self):
        self.send_signal(self.widget.Inputs.time_series, self.data)
        output = self.get_output(self.widget.Outputs.time_series)
        # first item is selected and computed
        self.assertEqual(len(output.domain), len(self.data.domain) + 1)
        self.assertTrue("Latitude [°] (diff; order=1)" in output.domain)
        # select some items
        select_rows(self.widget.view, [2, 3, 4])
        output = self.get_output(self.widget.Outputs.time_series)
        self.assertEqual(len(output.domain), len(self.data.domain) + 3)
        # send None
        self.send_signal(self.widget.Inputs.time_series, None)
        self.assertIsNone(self.get_output(self.widget.Outputs.time_series))
        # test if settings are properly restored
        self.send_signal(self.widget.Inputs.time_series, self.data)
        output = self.get_output(self.widget.Outputs.time_series)
        self.assertEqual(len(output.domain), len(self.data.domain) + 3)
        self.assertEqual(len(self.widget.selected), 3)
        self.assertFalse("Latitude [°] (diff; order=1)" in output.domain)


if __name__ == "__main__":
    unittest.main()
