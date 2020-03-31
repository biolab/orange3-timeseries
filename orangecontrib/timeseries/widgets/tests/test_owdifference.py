import unittest
import numpy as np

from Orange.widgets.utils.itemmodels import select_rows
from orangewidget.tests.base import WidgetTest
from Orange.data import Table

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owdifference import OWDifference


class TestOWDifference(WidgetTest):

    def setUp(self):
        self.widget = self.create_widget(OWDifference)  # type: OWDifference
        url = "https://datasets.biolab.si/core/ewba-slovenia-illegal-dumpsites.tab"
        self.data = Timeseries.from_url(url)
        self.simple_data = Table('iris')

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

    def test_difference(self):
        w = self.widget
        w.calc_difference = True
        w.diff_order = 1
        w.shift_period = 1
        self.send_signal(w.Inputs.time_series, self.data[:6])
        w.selected = ['petal width']
        w.commit()
        out = self.get_output(w.Outputs.time_series).X[:, -1]
        true_out = np.asarray([np.nan, 0, 0, 0, 0, -0.2])
        np.testing.assert_array_equal(out, true_out)

        # test order always one, if shift > 1
        w.shift_period = 2
        w.diff_order = 5
        self.send_signal(w.Inputs.time_series, self.data[:6])
        w.selected = ['petal width']
        w.commit()
        out = self.get_output(w.Outputs.time_series).X[:, -1]
        true_out = np.asarray([np.nan, np.nan, 0, 0, 0, -0.2])
        np.testing.assert_array_equal(out, true_out)

    def test_qoutient(self):
        w = self.widget
        w.chosen_operation = w.Operation.QUOTIENT
        w.invert_direction = False
        w.shift_period = 1
        self.send_signal(w.Inputs.time_series, self.data[:6])
        w.selected = ['petal width']
        w.commit()
        out = self.get_output(w.Outputs.time_series).X[:, -1]
        true_out = np.asarray([1, 1, 1, 1, 2, np.nan])
        np.testing.assert_array_equal(out, true_out)

    def test_percent(self):
        w = self.widget
        w.chosen_operation = w.Operation.PERCENT
        w.invert_direction = False
        w.shift_period = 1
        self.send_signal(w.Inputs.time_series, self.data[:6])
        w.selected = ['petal width']
        w.commit()
        out = self.get_output(w.Outputs.time_series).X[:, -1]
        true_out = np.asarray([0, 0, 0, 0, 100, np.nan])
        np.testing.assert_array_equal(out, true_out)

    def test_order_spin(self):
        w = self.widget
        w.chosen_operation = w.Operation.DIFFERENCE
        w.shift_period = 1
        w.on_changed()
        self.assertTrue(w.order_spin.isEnabled())

        w.shift_period = 2
        w.on_changed()
        self.assertFalse(w.order_spin.isEnabled())
        
        w.shift_period = 1
        w.on_changed()
        self.assertTrue(w.order_spin.isEnabled())

        w.chosen_operation = w.Operation.QUOTIENT
        w.on_changed()
        self.assertFalse(w.order_spin.isEnabled())
        
        w.chosen_operation = w.Operation.DIFFERENCE
        w.on_changed()
        self.assertTrue(w.order_spin.isEnabled())

        w.chosen_operation = w.Operation.PERCENT
        w.on_changed()
        self.assertFalse(w.order_spin.isEnabled())

if __name__ == "__main__":
    unittest.main()
