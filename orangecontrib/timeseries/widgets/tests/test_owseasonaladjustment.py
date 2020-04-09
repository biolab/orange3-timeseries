import unittest

from Orange.data import Table
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owseasonaladjustment import OWSeasonalAdjustment


class TestOWSeasonalAdjustment(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWSeasonalAdjustment)  # type: OWSeasonalAdjustment

    def test_negative_values(self):
        """
        Multiplicative seasonality does not work if there are negative
        values.
        GH-35
        """
        w = self.widget
        table = Timeseries.from_file("iris")
        table.X[1, 1] = -1
        w.decomposition = 1
        w.autocommit = True
        self.assertFalse(w.Error.seasonal_decompose_fail.is_shown())
        self.send_signal(w.Inputs.time_series, table)
        self.widget.view.selectAll()
        self.assertTrue(w.Error.seasonal_decompose_fail.is_shown())
        self.send_signal(w.Inputs.time_series, None)
        self.assertFalse(w.Error.seasonal_decompose_fail.is_shown())

    def test_too_many_periods(self):
        """
        Do not crash when there are too many season periods.
        GH-38
        """
        w = self.widget
        time_series = Timeseries.from_data_table(Table("iris")[::30])
        self.assertEqual(w.n_periods, 12)
        self.send_signal(w.Inputs.time_series, time_series)
        self.assertEqual(w.n_periods, 4)

    def test_not_enough_instances(self):
        """
        At least three instances are needed.
        GH-38
        """
        w = self.widget
        time_series = Timeseries.from_data_table(Table("iris")[:2])
        self.assertFalse(w.Error.not_enough_instances.is_shown())
        self.send_signal(w.Inputs.time_series, time_series)
        self.assertTrue(w.Error.not_enough_instances.is_shown())
        self.send_signal(w.Inputs.time_series, None)
        self.assertFalse(w.Error.not_enough_instances.is_shown())

    def test_output(self):
        """
        Adjusted values are added to the input data.
        """
        w = self.widget
        w.autocommit = True
        time_series = Timeseries.from_data_table(Table("iris"))
        self.send_signal(w.Inputs.time_series, time_series)
        selmodel = w.view.selectionModel()
        selmodel.select(w.model.index(0), selmodel.Select)
        self.assertGreater(len(self.get_output("Time series").domain),
                           len(time_series.domain))


if __name__ == "__main__":
    unittest.main()