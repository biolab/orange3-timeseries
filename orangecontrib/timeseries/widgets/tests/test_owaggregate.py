import unittest

import numpy as np

from Orange.data import Domain, DiscreteVariable, Table
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owaggregate import OWAggregate
from orangecontrib.timeseries.agg_funcs import AGG_FUNCTIONS


class TestOWAggregate(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWAggregate)  # type: OWAggregate
        self.time_series = Timeseries.from_file("airpassengers")

    def test_output_metas(self):
        """
        Do not create 3-dimensional numpy metas array.
        GH-44
        """
        w = self.widget
        new_domain = Domain(
            attributes=self.time_series.domain.attributes,
            class_vars=self.time_series.domain.class_vars,
            metas=[DiscreteVariable("meta", values=["0"])]
        )
        data = self.time_series.transform(new_domain)
        data.metas = np.zeros((144, 1), dtype=object)
        self.assertEqual(len(data.metas.shape), 2)
        self.send_signal(w.Inputs.time_series, data)
        w.controls.autocommit.click()
        output = self.get_output(w.Outputs.time_series)
        self.assertEqual(len(output.metas.shape), 2)

    def test_no_datetime(self):
        """ Raise error if no data with TimeVariable """
        w = self.widget
        table = Table.from_file('iris')
        self.send_signal(w.Inputs.time_series, self.time_series)
        self.assertFalse(w.Error.no_time_variable.is_shown())
        self.send_signal(w.Inputs.time_series, table)
        self.assertTrue(w.Error.no_time_variable.is_shown())
        self.send_signal(w.Inputs.time_series, self.time_series)
        self.assertFalse(w.Error.no_time_variable.is_shown())

    def test_tz_aggregation(self):
        w = self.widget
        self.send_signal(w.Inputs.time_series, self.time_series[:20])
        w.controls.autocommit.click()
        output = self.get_output(w.Outputs.time_series)
        self.assertEqual(output[0][0], "1949-01-01")

    def test_saved_selection(self):
        self.send_signal(self.widget.Inputs.time_series, self.time_series)
        # test default
        self.assertEqual(self.widget.agg_funcs[0], AGG_FUNCTIONS[0])
        # change aggregation
        self.widget.model[0][1] = AGG_FUNCTIONS[1]
        self.send_signal(self.widget.Inputs.time_series, None)
        self.assertEqual(len(self.widget.model), 0)
        # restore previous settings
        self.send_signal(self.widget.Inputs.time_series, self.time_series)
        self.assertEqual(self.widget.model[0][1], AGG_FUNCTIONS[1])


if __name__ == "__main__":
    unittest.main()
