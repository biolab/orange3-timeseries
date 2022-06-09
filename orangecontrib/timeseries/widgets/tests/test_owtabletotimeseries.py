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
        model = w.controls.order.model()
        self.assertEqual(len(model), 4)
        new_domain = Domain(data.domain[:6], metas=[data.domain[6]])
        new_data = Table.from_table(new_domain, data)
        self.send_signal(w.Inputs.data, new_data)
        self.assertEqual(len(model), 4)

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

        x, y, m = (ContinuousVariable(n) for n in "xym")
        domain = Domain(
            [DiscreteVariable("a", values=tuple("abc")), x, y],
            DiscreteVariable("c"),
            [m])
        xs = sp.csr_matrix([[0, 1, 0], [2, 0, np.nan], [0, -1, 2]])
        ys = sp.csr_matrix([[0], [1], [np.nan]])
        ms = sp.csr_matrix([[0], [3], [np.nan]])
        data = Table.from_numpy(domain, xs, ys, ms)
        self.send_signal(widget.Inputs.data, data)

        widget.order = x
        widget.commit.now()
        out = self.get_output(widget.Outputs.time_series)
        np.testing.assert_equal(
            out.X, [[0, -1, 2], [2, 0, np.nan], [0, 1, 0]])

        widget.order = y
        widget.commit.now()
        out = self.get_output(widget.Outputs.time_series)
        np.testing.assert_equal(
            out.X, [[0, 1, 0], [0, -1, 2]])
        self.assertTrue(widget.Information.nan_times.is_shown())

        widget.order = m
        widget.commit.now()
        out = self.get_output(widget.Outputs.time_series)
        np.testing.assert_equal(
            out.X, [[0, 1, 0], [2, 0, np.nan]])
        self.assertTrue(widget.Information.nan_times.is_shown())

        widget.order = x
        widget.commit.now()
        self.assertFalse(widget.Information.nan_times.is_shown())

        widget.order = m
        widget.commit.now()
        self.assertTrue(widget.Information.nan_times.is_shown())

        self.send_signal(widget.Inputs.data, None)
        self.assertFalse(widget.Information.nan_times.is_shown())


if __name__ == "__main__":
    unittest.main()
