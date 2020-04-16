import unittest

from Orange.data import Table
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owspiralogram import OWSpiralogram
from Orange.widgets.tests.utils import simulate
from Orange.widgets.settings import Context


class TestOWSpiralogram(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWSpiralogram)  # type: OWSpiralogram
        self.passengers = Timeseries.from_file("airpassengers")
        self.philadelphia = Timeseries.from_url('http://datasets.orange.biolab.si/core/philadelphia-crime.csv.xz')

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
        url = "http://file.biolab.si/datasets/cyber-security-breaches.tab"
        time_series2 = Timeseries.from_url(url)
        self.send_signal(w.Inputs.time_series, self.passengers)
        self.select_item(w, 0)
        output1 = self.get_output(w.Outputs.time_series)
        self.send_signal(w.Inputs.time_series, time_series2)
        self.select_item(w, 0)
        output2 = self.get_output(w.Outputs.time_series)
        self.assertNotEqual(output1, output2)

    def test_no_datetime(self):
        """ Raise error if no data with TimeVariable """
        w = self.widget
        table = Table.from_file('iris')
        self.send_signal(w.Inputs.time_series, self.passengers)
        self.assertFalse(w.Error.no_time_variable.is_shown())
        self.send_signal(w.Inputs.time_series, table)
        self.assertTrue(w.Error.no_time_variable.is_shown())
        self.send_signal(w.Inputs.time_series, self.passengers)
        self.assertFalse(w.Error.no_time_variable.is_shown())

    def test_tz_aggregation(self):
        """ Aggregation should consider timezone """
        w = self.widget
        data = self.passengers[:20]
        self.send_signal(w.Inputs.time_series, data)
        # select the first item
        self.select_item(w, 0)
        output = self.get_output(w.Outputs.time_series)
        self.assertEqual(output[0][0], "1949-01-01")

    def test_cb_axes(self):
        """ Test that all possible axes work, including discrete variables. """
        w = self.widget
        self.send_signal(w.Inputs.time_series, self.philadelphia)
        # test all possibilities for Y axis
        simulate.combobox_run_through_all(w.combo_ax2)
        # test all possibilities for radial
        simulate.combobox_run_through_all(w.combo_ax1)

    def test_time_variable(self):
        """ Spiralogram should work with TimeVariable. """
        w = self.widget
        self.send_signal(w.Inputs.time_series, self.philadelphia)
        # select time variable
        simulate.combobox_activate_item(w.attr_cb, 'Datetime')
        # test all possibilities for aggregations
        simulate.combobox_run_through_all(w.combo_func)

    def test_migrate_settings_from_version_1_disc(self):
        settings = {
            '__version__': 1,
            'context_settings': [
                Context(values={'agg_attr': ([('Type', 101)], -3),
                                'agg_func': (0, -2),
                                'ax1': ('months', -2),
                                'ax2': ('years', -2)})],
            'controlAreaVisible': True,
            'invert_date_order': False,
            'savedWidgetGeometry': None
        }
        w = self.create_widget(OWSpiralogram, stored_settings=settings)
        self.send_signal(w.Inputs.time_series, self.philadelphia, widget=w)
        self.assertEqual(w.agg_attr.name, 'Type')
        self.assertEqual(w.agg_func, 'Mode')

    def test_migrate_settings_from_version_1_time(self):
        settings = {
            '__version__': 1,
            'context_settings': [
                Context(values={'agg_attr': ([('Datetime', 104)], -3),
                                'agg_func': (12, -2),
                                'ax1': ('months', -2),
                                'ax2': ('years', -2)})],
            'controlAreaVisible': True,
            'invert_date_order': False,
            'savedWidgetGeometry': None
        }
        w = self.create_widget(OWSpiralogram, stored_settings=settings)
        self.send_signal(w.Inputs.time_series, self.philadelphia, widget=w)
        self.assertEqual(w.agg_attr.name, 'Datetime')
        self.assertEqual(w.agg_func, 'Mean')


if __name__ == "__main__":
    unittest.main()
