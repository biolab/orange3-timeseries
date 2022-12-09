import unittest

import numpy as np
from AnyQt.QtCore import QT_VERSION_INFO

from orangewidget.tests.base import WidgetTest
from Orange.widgets.utils.itemmodels import select_rows
from Orange.data import \
    Domain, Table, ContinuousVariable, DiscreteVariable, StringVariable

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owdifference import OWDifference


class TestOWDifference(WidgetTest):
    def setUp(self):
        self.widget: OWDifference = self.create_widget(OWDifference)

        domain = Domain([ContinuousVariable(n) for n in "abc"]
                        + [DiscreteVariable("d", values=("d", "e"))],
                        ContinuousVariable("y"),
                        [StringVariable("s")])
        self.data = Timeseries.from_numpy(
            domain,
            [[4, 5, 8, 0],
             [1, -2, 0, 1],
             [3, np.nan, 2, 0],
             [7, np.nan, 1, 0]],
            [1, 2, 3, 4], [["foo"]] * 4
        )

    def test_saved_selection(self):
        widget = self.widget
        self.send_signal(widget.Inputs.time_series, self.data)
        select_rows(widget.view, [1, 2])
        self.assertEqual(widget.selection, ["b", "c"])

        self.send_signal(widget.Inputs.time_series, None)
        self.assertEqual(widget.selection, [])

        self.send_signal(self.widget.Inputs.time_series, self.data)
        self.assertEqual(widget.selection, ["b", "c"])

        self.send_signal(widget.Inputs.time_series, None)
        self.assertEqual(widget.selection, [])

        self.send_signal(self.widget.Inputs.time_series, self.data[:, 2:])
        self.assertEqual(widget.selection, ["c"])

    def test_difference(self):
        widget = self.widget
        widget.operation = widget.Diff

        widget.shift_period = 1
        widget.invert_direction = False
        widget.assume_zero_before = False
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[np.nan, np.nan, np.nan],
                      [-3, -7, -8],
                      [2, np.nan, 2],
                      [4, np.nan, -1]])

        widget.assume_zero_before = True
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[4, 5, 8],
                      [-3, -7, -8],
                      [2, np.nan, 2],
                      [4, np.nan, -1]])

        widget.shift_period = 1
        widget.invert_direction = True
        widget.assume_zero_before = False
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[3, 7, 8],
                      [-2, np.nan, -2],
                      [-4, np.nan, 1],
                      [np.nan, np.nan, np.nan]])

        widget.shift_period = 1
        widget.invert_direction = True
        widget.assume_zero_before = True  # This must be ignored!
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[3, 7, 8],
                      [-2, np.nan, -2],
                      [-4, np.nan, 1],
                      [np.nan, np.nan, np.nan]])

        widget.shift_period = 2
        widget.invert_direction = False
        widget.assume_zero_before = False
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan],
                      [-1, np.nan, -6],
                      [6, np.nan, 1]])

        widget.shift_period = 2
        widget.invert_direction = False
        widget.assume_zero_before = True
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[4, 5, 8],
                      [1, -2, 0],
                      [-1, np.nan, -6],
                      [6, np.nan, 1]])

        widget.shift_period = 2
        widget.invert_direction = True
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[1, np.nan, 6],
                      [-6, np.nan, -1],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan]])

        widget.shift_period = 2
        widget.invert_direction = True
        widget.assume_zero_before = True  # This must be ignored!
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[1, np.nan, 6],
                      [-6, np.nan, -1],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan]])

        widget.shift_period = 3
        widget.invert_direction = False
        widget.assume_zero_before = False
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan],
                      [3, np.nan, -7]])

        widget.shift_period = 3
        widget.invert_direction = False
        widget.assume_zero_before = True
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[4, 5, 8],
                      [1, -2, 0],
                      [3, np.nan, 2],
                      [3, np.nan, -7]])

        widget.shift_period = 3
        widget.invert_direction = True
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[-3, np.nan, 7],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan]])

        for widget.shift_period in (4, 5, 10):
            for widget.invert_direction in (False, True):
                for widget.assume_zero_before in (False, True):
                    _, columns = widget.compute(self.data, list("abc"))
                    if not widget.assume_zero_before or widget.invert_direction:
                        np.testing.assert_equal(
                            columns, [[np.nan, np.nan, np.nan],
                                      [np.nan, np.nan, np.nan],
                                      [np.nan, np.nan, np.nan],
                                      [np.nan, np.nan, np.nan]])
                    else:
                        np.testing.assert_equal(columns, self.data.X[:, :3])

    def test_difference2(self):
        widget = self.widget
        widget.operation = widget.Diff2

        widget.shift_period = 1
        widget.invert_direction = False
        widget.assume_zero_before = False
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan],
                      [5, np.nan, 10],
                      [2, np.nan, -3]])

        widget.shift_period = 1
        widget.invert_direction = False
        widget.assume_zero_before = True
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[4, 5, 8],
                      [-7, -12, -16],
                      [5, np.nan, 10],
                      [2, np.nan, -3]])

        widget.shift_period = 1
        widget.invert_direction = True
        widget.assume_zero_before = False
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[5, np.nan, 10],
                      [2, np.nan, -3],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan]])

        widget.shift_period = 1
        widget.invert_direction = True
        widget.assume_zero_before = True  # This must be ignored!
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_equal(
            columns, [[5, np.nan, 10],
                      [2, np.nan, -3],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan]])

    def test_quotient(self):
        widget = self.widget
        widget.operation = widget.Quot

        widget.shift_period = 1
        widget.invert_direction = False
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_almost_equal(
            columns, [[np.nan, np.nan, np.nan],
                      [1 / 4, -2 / 5, 0 / 8],
                      [3 / 1, np.nan, np.nan],
                      [7 / 3, np.nan, 1 / 2]])

        widget.shift_period = 1
        widget.invert_direction = True
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_almost_equal(
            columns, [[4, -5 / 2, np.nan],
                      [1 / 3, np.nan, 0],
                      [3 / 7, np.nan, 2],
                      [np.nan, np.nan, np.nan]])

        widget.shift_period = 2
        widget.invert_direction = False
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_almost_equal(
            columns, [[np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan],
                      [3 / 4, np.nan, 2 / 8],
                      [7 / 1, np.nan, np.nan]])

        widget.shift_period = 2
        widget.invert_direction = True
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_almost_equal(
            columns, [[4 / 3, np.nan, 8 / 2],
                      [1 / 7, np.nan, 0],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan]])

        widget.shift_period = 3
        widget.invert_direction = False
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_almost_equal(
            columns, [[np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan],
                      [7 / 4, np.nan, 1 / 8]])

        widget.shift_period = 3
        widget.invert_direction = True
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_almost_equal(
            columns, [[4 / 7, np.nan, 8 / 1],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan]])

        for widget.shift_period in (4, 5, 10):
            for widget.invert_direction in (False, True):
                _, columns = widget.compute(self.data, list("abc"))
                np.testing.assert_equal(
                    columns, [[np.nan, np.nan, np.nan],
                              [np.nan, np.nan, np.nan],
                              [np.nan, np.nan, np.nan],
                              [np.nan, np.nan, np.nan]])

    def test_percent(self):
        widget = self.widget
        widget.operation = widget.Perc

        widget.shift_period = 1
        widget.invert_direction = False
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_almost_equal(
            columns, [[np.nan, np.nan, np.nan],
                      [-75, -140, -100],
                      [200, np.nan, np.nan],
                      [400 / 3, np.nan, -50]])

        widget.shift_period = 1
        widget.invert_direction = True
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_almost_equal(
            columns, [[300, -350, np.nan],
                      [-200 / 3, np.nan, -100],
                      [-400 / 7, np.nan, 100],
                      [np.nan, np.nan, np.nan]])

        widget.shift_period = 2
        widget.invert_direction = False
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_almost_equal(
            columns, [[np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan],
                      [-25, np.nan, -75],
                      [600, np.nan, np.nan]])

        widget.shift_period = 2
        widget.invert_direction = True
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_almost_equal(
            columns, [[100 / 3, np.nan, 300],
                      [-600 / 7, np.nan, -100],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan]])

        widget.shift_period = 3
        widget.invert_direction = False
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_almost_equal(
            columns, [[np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan],
                      [75, np.nan, -700 / 8]])

        widget.shift_period = 3
        widget.invert_direction = True
        _, columns = widget.compute(self.data, list("abc"))
        np.testing.assert_almost_equal(
            columns, [[-300 / 7, np.nan, 700],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan],
                      [np.nan, np.nan, np.nan]])

        for widget.shift_period in (4, 5, 10):
            for widget.invert_direction in (False, True):
                _, columns = widget.compute(self.data, list("abc"))
                np.testing.assert_equal(
                    columns, [[np.nan, np.nan, np.nan],
                              [np.nan, np.nan, np.nan],
                              [np.nan, np.nan, np.nan],
                              [np.nan, np.nan, np.nan]])

    def test_commits(self):
        def checkout(cols):
            out = self.get_output(widget.Outputs.time_series)
            if cols is None:
                self.assertIsNone(out)
            else:
                np.testing.assert_equal(out.X, np.column_stack((self.data.X, cols)))
                np.testing.assert_equal(out.Y, self.data.Y)
                np.testing.assert_equal(out.metas, self.data.metas)

        def sq(r, c, add):
            return np.arange(add, add + r * c, dtype=float).reshape(r, c)

        widget = self.widget
        widget.selection = list("abc")
        widget.shift_period = 1
        widget.operation = 2

        widget.compute = lambda data, names: (
            tuple(ContinuousVariable(n + "x") for n in names),
            sq(len(data), len(names), widget.operation + widget.shift_period * 10))

        checkout(None)

        self.send_signal(widget.Inputs.time_series, self.data)
        checkout(sq(4, 3, 12))

        self.send_signal(widget.Inputs.time_series, None)
        checkout(None)

        self.send_signal(widget.Inputs.time_series, self.data)
        checkout(sq(4, 3, 12))

        if QT_VERSION_INFO < (5, 15):
            return
        widget.operation = 3
        widget.controls.operation.group.idClicked.emit(3)
        checkout(sq(4, 3, 13))

        widget.shift_period = 2
        widget.controls.shift_period.valueChanged.emit(2)
        checkout(sq(4, 3, 23))

        select_rows(widget.view, [0, 2])

    def test_in_out(self):
        widget = self.widget

        def checkout(cols, attrs):
            out = self.get_output(widget.Outputs.time_series)
            if cols is None:
                self.assertIsNone(out)
            else:
                np.testing.assert_equal(out.X, np.column_stack((self.data.X, cols)))
                np.testing.assert_equal(out.Y, self.data.Y)
                np.testing.assert_equal(out.metas, self.data.metas)
                self.assertEqual(
                    [attr.name for attr in out.domain.attributes],
                    [attr.name for attr in self.data.domain.attributes] + attrs
                )

        checkout(None, [])

        self.send_signal(widget.Inputs.time_series, self.data)
        checkout(np.zeros((4, 0)), [])

        select_rows(widget.view, (0, 2))
        checkout(np.array([[np.nan, np.nan], [-3, -8], [2, 2], [4, -1]]),
                 ["Δa", "Δc"])

        self.send_signal(widget.Inputs.time_series, None)
        checkout(None, [])

    def test_convert_non_timeseries(self):
        self.send_signal(self.widget.Inputs.time_series, Table("iris"))
        self.assertIsInstance(self.widget.data, Timeseries)


if __name__ == "__main__":
    unittest.main()
