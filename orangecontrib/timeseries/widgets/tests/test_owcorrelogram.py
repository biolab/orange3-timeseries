import unittest

import numpy as np
from AnyQt.QtCore import QItemSelectionModel

from Orange.data import Table, Domain, ContinuousVariable
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owcorrelogram import OWCorrelogram


# This also test PeriodBase class

class TestCorrelogramWidget(WidgetTest):
    def setUp(self):
        self.widget: OWCorrelogram = self.create_widget(OWCorrelogram)

    def test_nan_timeseries(self):
        """
        Widget used to crash because interpolation crashed when
        there was a column with all nans or all nuns and only one number.
        Now interpolation is skipped.
        GH-27
        """
        time_series = Timeseries.from_list(
            Domain(attributes=[ContinuousVariable("a"), ContinuousVariable("b")]),
            list(zip(list(range(5)), list(range(5))))
        )
        with time_series.unlocked():
            time_series.X[:, 1] = np.nan
        self.send_signal(self.widget.Inputs.time_series, time_series)
        with time_series.unlocked():
            time_series.X[2, 1] = 42
        self.send_signal(self.widget.Inputs.time_series, time_series)

    def test_no_instances(self):
        ts = Timeseries.from_file("airpassengers")

        self.assertFalse(self.widget.Error.no_instances.is_shown())

        self.send_signal(self.widget.Inputs.time_series, ts[:1])
        self.assertTrue(self.widget.Error.no_instances.is_shown())

        self.send_signal(self.widget.Inputs.time_series, ts)
        self.assertFalse(self.widget.Error.no_instances.is_shown())

        self.send_signal(self.widget.Inputs.time_series, ts[:1])
        self.assertTrue(self.widget.Error.no_instances.is_shown())

        self.send_signal(self.widget.Inputs.time_series, None)
        self.assertFalse(self.widget.Error.no_instances.is_shown())

    def test_no_numeric(self):
        self.send_signal(self.widget.Inputs.time_series, Table("titanic"))
        self.assertTrue(self.widget.Error.no_variables.is_shown())

        self.send_signal(self.widget.Inputs.time_series, None)
        self.assertFalse(self.widget.Error.no_variables.is_shown())

    def test_selection_persistence(self):
        data = Timeseries.from_numpy(
            Domain([ContinuousVariable(n) for n in "abcd"]),
            np.arange(16).reshape(4, 4))
        self.send_signal(self.widget.Inputs.time_series, data)

        index = self.widget.model.index
        selmodel = self.widget.selectionModel
        selmodel.select(index(1), QItemSelectionModel.ClearAndSelect)
        selmodel.select(index(3), QItemSelectionModel.Select)

        self.assertEqual(self.widget.selection, ["b", "d"])

        self.send_signal(self.widget.Inputs.time_series, None)
        self.assertEqual(self.widget.selection, [])

        self.send_signal(self.widget.Inputs.time_series, data)
        self.assertEqual(self.widget.selection, ["b", "d"])

        self.send_signal(self.widget.Inputs.time_series, None)
        self.assertEqual(self.widget.selection, [])

        self.send_signal(self.widget.Inputs.time_series, data[:, 1:])
        self.assertEqual(self.widget.selection, ["b", "d"])

        self.send_signal(self.widget.Inputs.time_series, None)
        self.assertEqual(self.widget.selection, [])

        self.send_signal(self.widget.Inputs.time_series, data)
        self.assertEqual(self.widget.selection, ["b", "d"])

        self.send_signal(self.widget.Inputs.time_series, data[:, 3:])
        self.assertEqual(self.widget.selection, ["d"])


if __name__ == "__main__":
    unittest.main()
