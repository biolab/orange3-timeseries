import unittest

import numpy as np
import scipy.sparse as sp

from Orange.data import Table, Domain, DiscreteVariable, ContinuousVariable
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owtabletotimeseries import OWTableToTimeseries


class TestAsTimeSeriesWidget(WidgetTest):
    def setUp(self):
        self.widget = self.create_widget(OWTableToTimeseries)  # type: OWTableToTimeseries

    def test_time_as_metas(self):
        """
        As Timeseries should accept attributes from X and metas.
        """
        w = self.widget
        data = Table.from_url("http://file.biolab.si/datasets/cyber-security-breaches.tab")[:20]
        self.send_signal(w.Inputs.data, data)
        self.assertEqual(len(w.attrs_model), 4)
        new_domain = Domain(data.domain[:6], metas=[data.domain[6]])
        new_data = Table.from_table(new_domain, data)
        self.send_signal(w.Inputs.data, new_data)
        self.assertEqual(len(w.attrs_model), 4)

    def test_timeseries_column_nans(self):
        """
        When cannot create Timeseries make sure output is None.
        GH-30
        """
        w = self.widget
        data = Table("iris")[:2].copy()
        self.assertFalse(w.Information.nan_times.is_shown())
        self.send_signal(w.Inputs.data, data)
        self.assertFalse(w.Information.nan_times.is_shown())
        self.assertIsInstance(self.get_output(w.Outputs.time_series), Timeseries)
        with data.unlocked():
            data.X[:, 0] = np.nan
        self.send_signal(w.Inputs.data, data)
        self.assertTrue(w.Information.nan_times.is_shown())
        self.assertIsNone(self.get_output(w.Outputs.time_series))

    def test_timeserise_sparse(self):
        widget = self.widget
        widget.radio_sequential = 0

        domain = Domain(
            [DiscreteVariable("a", values=tuple("abc")),
             ContinuousVariable("x"),
             ContinuousVariable("y")],
            DiscreteVariable("c"),
            [ContinuousVariable("m")])
        x = sp.csr_matrix([[0, 1, 0], [2, 0, np.nan], [0, -1, 2]])
        y = sp.csr_matrix([[0], [1], [np.nan]])
        m = sp.csr_matrix([[0], [3], [np.nan]])
        data = Table.from_numpy(domain, x, y, m)
        self.send_signal(widget.Inputs.data, data)

        widget.selected_attr = "x"
        widget.commit()
        out = self.get_output(widget.Outputs.time_series)
        np.testing.assert_equal(
            out.X, [[0, -1, 2], [2, 0, np.nan], [0, 1, 0]])

        widget.selected_attr = "y"
        widget.commit()
        out = self.get_output(widget.Outputs.time_series)
        np.testing.assert_equal(
            out.X, [[0, 1, 0], [0, -1, 2]])
        self.assertTrue(widget.Information.nan_times.is_shown())

        widget.selected_attr = "m"
        widget.commit()
        out = self.get_output(widget.Outputs.time_series)
        np.testing.assert_equal(
            out.X, [[0, 1, 0], [2, 0, np.nan]])
        self.assertTrue(widget.Information.nan_times.is_shown())

        widget.selected_attr = "x"
        widget.commit()
        self.assertFalse(widget.Information.nan_times.is_shown())

        widget.selected_attr = "m"
        widget.commit()
        self.assertTrue(widget.Information.nan_times.is_shown())

        self.send_signal(widget.Inputs.data, None)
        self.assertFalse(widget.Information.nan_times.is_shown())

    def test_non_cont_sequental(self):
        """
        Widget can create sequental time variable and values
        if input data does not have any continuous variables.
        GH-40
        """
        w = self.widget
        table = Table("titanic")
        self.send_signal(w.Inputs.data, table)
        self.assertIsNone(self.get_output(w.Outputs.time_series))
        w.controls.radio_sequential.buttons[1].click()
        self.assertIsNotNone(self.get_output(w.Outputs.time_series))


if __name__ == "__main__":
    unittest.main()
