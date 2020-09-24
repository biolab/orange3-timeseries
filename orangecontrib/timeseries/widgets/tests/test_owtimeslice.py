import os
import unittest

from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owtimeslice import OWTimeSlice


class TestTimeSliceWidget(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWTimeSlice)
        self.dataset_dir = os.path.join(os.path.dirname(__file__), 'datasets')

    def test_multiple_on_same_dt(self):
        # GH-115
        data = Timeseries.from_file(
            os.path.join(self.dataset_dir, 'multipleonsamedt.csv')
        )
        self.widget.set_data(data)
        self.assertTrue(self.widget.Outputs.subset)

    def test_numeric_timedelta(self):
        # GH-110
        data = Timeseries.from_file(
            os.path.join(self.dataset_dir, 'numericdt.csv')
        )
        self.widget.set_data(data)
        self.assertTrue(self.widget.Outputs.subset)

    def test_day_timedelta(self):
        data = Timeseries.from_file(
            os.path.join(self.dataset_dir, 'daydt.csv')
        )
        self.widget.set_data(data)
        self.assertTrue(self.widget.Outputs.subset)

    def test_month_timedelta(self):
        data = Timeseries.from_file('airpassengers')
        self.widget.set_data(data)
        self.assertTrue(self.widget.Outputs.subset)

    def test_year_timedelta(self):
        data = Timeseries.from_file(
            os.path.join(self.dataset_dir, 'yeardt.csv')
        )
        self.widget.set_data(data)
        self.assertTrue(self.widget.Outputs.subset)

    def test_unsorted_ts(self):
        data = Timeseries.from_file(
            os.path.join(self.dataset_dir, 'unsortedts.csv')
        )
        self.widget.set_data(data)
        self.assertTrue(self.widget.Outputs.subset)

    def test_no_timedelta_ts(self):
        # GH-126
        data = Timeseries.from_file(
            os.path.join(self.dataset_dir, 'notddt.csv')
        )
        self.widget.set_data(data)
        self.assertTrue(self.widget.Outputs.subset)


if __name__ == "__main__":
    unittest.main()