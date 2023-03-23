import warnings
import unittest
from unittest.mock import Mock

import numpy as np

from AnyQt.QtGui import QColor
from AnyQt.QtCore import Qt
from AnyQt.QtWidgets import QApplication

from orangewidget.tests.base import GuiTest

from Orange.data import Table, DiscreteVariable, ContinuousVariable, Domain, \
    TimeVariable, Variable, StringVariable
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.owspiralogram import OWSpiralogram, \
    SegmentItem, AggOptionsModel, AggItems, BlockData


class SegmentItemTest(GuiTest):
    def test_drawing(self):
        # just test it doesn't crash or warn
        warnings.simplefilter("error")
        color = QColor(1, 2, 3)
        tooltip = "foo"

        for ngroups in (1, 3, 10):
            for nperiods in (1, 3, 10):
                for r in range(ngroups):
                    for x in range(nperiods):
                        SegmentItem.from_coordinates(
                            x, r, 100, nperiods, ngroups, color, tooltip,
                            r % 2 == 0, Mock())

    def test_select_hover(self):
        segment = SegmentItem.from_coordinates(
            1, 2, 100, 4, 4, QColor(1, 2, 3), "foo", False)

        def pen():
            p = segment.pen()
            return (p.color().name(), p.width(), p.style())

        orig_pen = pen()
        segment.set_selected(False)
        self.assertEqual(pen(), orig_pen)

        segment.set_selected(True)
        sel_pen = pen()
        self.assertNotEqual(orig_pen, sel_pen)

        segment.hoverEnterEvent(Mock())
        sel_hover_pen = pen()
        self.assertNotEqual(orig_pen, sel_hover_pen)
        self.assertNotEqual(sel_pen, sel_hover_pen)

        segment.hoverLeaveEvent(Mock())
        self.assertEqual(pen(), sel_pen)

        segment.set_selected(False)
        segment.hoverEnterEvent(Mock())
        self.assertNotEqual(orig_pen, pen())
        self.assertNotEqual(sel_pen, pen())
        self.assertNotEqual(sel_hover_pen, pen())

        segment.hoverLeaveEvent(Mock())
        self.assertEqual(pen(), orig_pen)

    def test_onclick(self):
        callback = Mock()
        segment = SegmentItem.from_coordinates(
            1, 2, 100, 4, 4, QColor(1, 2, 3), "foo", False, callback)
        event = Mock()
        segment.mousePressEvent(event)
        callback.assert_called_with(segment, event)


class AggOptionsModelTest(GuiTest):
    def test_model(self):
        def test_discrete():
            for i, desc in enumerate(AggItems.values()):
                self.assertIs(
                    model.flags(index(i)) & Qt.ItemIsEnabled == Qt.ItemIsEnabled,
                    desc.supports_discrete, f"for {desc.long_desc}")

        def test_continuous():
            for i, desc in enumerate(AggItems.values()):
                self.assertEqual(
                    model.flags(index(i)) & Qt.ItemIsEnabled, Qt.ItemIsEnabled,
                    f"for {desc.long_desc}")

        dvar = DiscreteVariable("x", values=tuple("abc"))
        cvar = ContinuousVariable("y")

        model = AggOptionsModel(dvar)
        index = model.index
        self.assertEqual(len(model), len(AggItems))

        test_discrete()
        model.set_variable(cvar)
        test_continuous()

        model.set_variable(dvar)
        test_discrete()

        # Whatever, just don't crash
        model.set_variable(None)

        # Whatever, just don't crash
        model = AggOptionsModel(None)

        model = AggOptionsModel(cvar)
        test_continuous()


class TestOWSpiralogram(WidgetTest):
    def setUp(self):
        self.widget: OWSpiralogram = self.create_widget(OWSpiralogram)

        a = DiscreteVariable("a", values=tuple("abc"))
        b = DiscreteVariable("b", values=tuple("defgh"))
        c = ContinuousVariable("c")
        d = TimeVariable("d")
        day = 24 * 60 * 60
        x = np.array([[0., 0, 1, 0 * day],
                      [0, 0, 2, 1 * day],
                      [0, 0, 3, 2 * day],
                      [0, 2, 4, 3 * day],
                      [1, 0, 5, 4 * day],
                      [1, 1, 6, 5 * day],
                      [1, 2, 7, 6 * day],
                      [1, 3, 8, 7 * day],
                      [1, 4, 9, 8 * day],
                      [2, 2, 20, (365 + 9) * day]])
        self.data = Table.from_numpy(Domain([a, b, c, d]), x)

        self.time_data = Timeseries.from_data_table(self.data, d)

        self.useless_data = \
            Table.from_list(Domain([], None, [StringVariable("s")]),
                            [["foo"]])

    def _change_var(self, combo, i):
        combo.setCurrentIndex(i)
        combo.activated.emit(i)

    def change_x(self, i):
        self._change_var(self.widget.controls.x_var, i)

    def change_r(self, i):
        self._change_var(self.widget.controls.r_var, i)

    def change_color(self, i):
        self._change_var(self.widget.controls.color_var, i)

    def test_x_r_changes_blocks_statistics(self):
        widget = self.widget
        a, b, *_ = self.data.domain.attributes

        self.send_signal(widget.Inputs.time_series, self.data)
        QApplication.processEvents()  # reblock uses single shot timer

        self.assertIs(widget.x_var, a)
        self.assertIsNone(widget.r_var)
        self.assertEqual(widget.nperiods, 3)
        self.assertEqual(widget.ngroups, 1)

        out = self.get_output(widget.Outputs.statistics)
        domain = out.domain
        self.assertEqual(len(domain.attributes), 2)
        self.assertIs(domain.attributes[0], a)
        self.assertIsInstance(domain.attributes[1], ContinuousVariable)
        self.assertIsNone(out.domain.class_var)
        np.testing.assert_equal(out.X, [[0, 4], [1, 5], [2, 1]])

        self.change_x(1)
        self.assertIs(widget.x_var, b)
        self.assertEqual(widget.nperiods, 5)
        self.assertEqual(widget.ngroups, 1)

        out = self.get_output(widget.Outputs.statistics)
        domain = out.domain
        self.assertEqual(len(domain.attributes), 2)
        self.assertIs(domain.attributes[0], b)
        self.assertIsInstance(domain.attributes[1], ContinuousVariable)
        self.assertIsNone(out.domain.class_var)
        np.testing.assert_equal(out.X, [[0, 4], [1, 1], [2, 3], [3, 1], [4, 1]])

        self.change_r(1)
        self.assertIs(widget.x_var, b)
        self.assertIs(widget.r_var, a)
        self.assertEqual(widget.nperiods, 5)
        self.assertEqual(widget.ngroups, 3)

        out = self.get_output(widget.Outputs.statistics)
        domain = out.domain
        self.assertEqual(len(domain.attributes), 3)
        self.assertEqual(domain.attributes[:2], (b, a))
        self.assertIsInstance(domain.attributes[2], ContinuousVariable)
        self.assertIsNone(out.domain.class_var)
        np.testing.assert_equal(
            out.X,
            [[0, 0, 3],
             [0, 1, 1],
             [1, 1, 1],
             [2, 0, 1],
             [2, 1, 1],
             [2, 2, 1],
             [3, 1, 1],
             [4, 1, 1]])

    def test_x_r_changes_bins(self):
        widget = self.widget
        a, b, c, d, *_ = self.data.domain.attributes

        self.send_signal(widget.Inputs.time_series, self.data)

        self.assertTrue(widget.x_binner.box.isHidden())
        self.assertTrue(widget.r_binner.box.isHidden())

        self.change_x(2)  # [a, b, c][2]
        self.assertFalse(widget.x_binner.box.isHidden())
        self.assertTrue(widget.r_binner.box.isHidden())
        self.assertNotEqual(widget.x_binner.binnings, [])
        # Not checking the actual content -- this needs to be checked in
        # tests for Binner.

        self.change_r(3)  # [None. a, b, c][3]
        self.assertFalse(widget.x_binner.box.isHidden())
        self.assertFalse(widget.r_binner.box.isHidden())
        self.assertNotEqual(widget.r_binner.binnings, [])

        recompute = widget.x_binner.recompute_binnings = Mock()
        self.change_x(1)  # b, discrete
        recompute.assert_called_with(None, False)
        self.change_x(2)  # c, continuous
        np.testing.assert_equal(recompute.call_args[0][0],
                                self.data.get_column(c))
        self.assertFalse(recompute.call_args[0][1])

        self.change_x(3)  # d, time
        np.testing.assert_equal(recompute.call_args[0][0],
                                self.data.get_column(d))
        self.assertTrue(recompute.call_args[0][1])

    def test_slider_track_doesnt_commit(self):
        widget = self.widget
        widget.commit_statistics = Mock()

        self.send_signal(widget.Inputs.time_series, self.data)
        self.change_x(2)  # [a, b, c][2]

        widget.commit_statistics.reset_mock()
        widget.x_binner.slider.sliderMoved.emit(0)
        widget.commit_statistics.assert_not_called()
        widget.x_binner.slider.sliderReleased.emit()
        widget.commit_statistics.assert_called_once()

    def test_update_agg_combo(self):
        widget = self.widget
        combo = widget.controls.aggregation
        model = combo.model()

        self.send_signal(widget.Inputs.time_series, self.data)

        self.change_color(3)  # c, continuous
        self.assertTrue(combo.isEnabled())
        self.assertFalse(any(map(model.is_disabled, AggItems)))

        widget.aggregation = "Mean value"

        self.change_color(2)  # b, discrete
        self.assertTrue(combo.isEnabled())
        self.assertTrue(any(map(model.is_disabled, AggItems)))

        self.assertNotEqual(widget.aggregation, "Mean value")

    def test_set_data_vars(self):
        widget = self.widget
        a, b, c, d, *_ = self.data.domain.attributes

        self.send_signal(widget.Inputs.time_series, self.data)
        self.assertTrue(all(isinstance(item, Variable)
                            for item in widget.x_model))

        self.send_signal(widget.Inputs.time_series, self.time_data)
        QApplication.processEvents()  # reblock uses single shot timer
        self.assertTrue(any(isinstance(item, Variable)
                            for item in widget.x_model))
        self.assertTrue(any(isinstance(item, str)
                            for item in widget.x_model))
        self.assertIsNotNone(self.get_output(widget.Outputs.statistics))

        self.send_signal(widget.Inputs.time_series, None)
        QApplication.processEvents()  # reblock uses single shot timer
        self.assertFalse(widget.x_model)
        self.assertIsNone(self.get_output(widget.Outputs.statistics))

        self.send_signal(widget.Inputs.time_series, self.data)
        QApplication.processEvents()  # reblock uses single shot timer
        assert self.get_output(widget.Outputs.statistics)

        self.send_signal(widget.Inputs.time_series, self.useless_data)
        self.assertIsNone(self.get_output(widget.Outputs.statistics))
        self.assertTrue(widget.Error.no_useful_vars.is_shown())

        self.send_signal(widget.Inputs.time_series, None)
        self.assertFalse(widget.Error.no_useful_vars.is_shown())

    def test_nperiods_ngroups_not_time(self):
        widget = self.widget
        a, b, c, d, *_ = self.data.domain.attributes

        self.assertEqual(widget.nperiods, 0)
        self.assertEqual(widget.ngroups, 0)

        self.send_signal(widget.Inputs.time_series, self.data)

        self.change_x(0)
        self.change_r(0)
        self.assertEqual(widget.nperiods, len(a.values))
        self.assertEqual(widget.ngroups, 1)

        self.change_x(1)
        self.assertEqual(widget.nperiods, len(b.values))
        self.assertEqual(widget.ngroups, 1)

        self.change_r(1)  # a
        self.assertEqual(widget.nperiods, len(b.values))
        self.assertEqual(widget.ngroups, len(a.values))

    def test_nperiods_ngroups_time_data(self):
        widget = self.widget
        self.send_signal(widget.Inputs.time_series, self.time_data)

        self.change_x(0)  # month of year
        self.assertEqual(widget.nperiods, 12)

        self.change_x(3)  # day of week
        self.assertEqual(widget.nperiods, 7)

    def test_is_time_period(self):
        widget = self.widget
        self.send_signal(widget.Inputs.time_series, self.time_data)

        self.change_x(0)
        self.assertTrue(widget.is_time_period)

        self.change_x(len(widget.x_model) - 1)
        self.assertFalse(widget.is_time_period)

    def test_update_flow(self):
        widget = self.widget
        self.send_signal(widget.Inputs.time_series, self.data)

        widget.commit_selection = Mock()  # called from reblock
        widget.commit_statistics = Mock()  # called from recompute
        widget.scene.clear = Mock()  # called from redraw

        for widget.data in (self.data, None):
            widget.selection = {0}
            widget.reblock()

            self.assertEqual(widget.selection, set())
            widget.commit_selection.assert_called()
            widget.commit_statistics.assert_called()
            widget.scene.clear.assert_called()

            widget.commit_selection.reset_mock()
            widget.commit_statistics.reset_mock()
            widget.scene.clear.reset_mock()

            if widget.data:
                widget.selection = {0}
            widget.recompute()

            if widget.data:
                self.assertEqual(widget.selection, {0})
            widget.commit_selection.assert_not_called()
            widget.commit_statistics.assert_called()
            widget.scene.clear.assert_called()

            widget.commit_statistics.reset_mock()
            widget.scene.clear.reset_mock()

            widget.redraw()
            widget.commit_selection.assert_not_called()
            widget.commit_statistics.assert_not_called()
            widget.scene.clear.assert_called()

            widget.commit_statistics.reset_mock()
            widget.scene.clear.reset_mock()

    def test_pending_selection(self):
        def commit_selection(*_):
            nonlocal comitted
            self.assertEqual(widget.selection, {(1, 0)})
            comitted = True

        comitted = False
        widget = self.widget
        widget.commit_selection = commit_selection
        widget._pending_selection = [(1, 0)]
        self.send_signal(widget.Inputs.time_series, self.data)
        QApplication.processEvents()  # reblock uses single shot timer
        self.assertTrue(comitted)

    def test_compute_block_data(self):
        widget = self.widget
        index_of = widget.x_model.indexOf
        self.send_signal(widget.Inputs.time_series, self.time_data)
        a, b, c, d, *_ = self.data.domain.attributes

        self.change_x(index_of(b))
        self.change_r(0)
        blocks = widget.compute_block_data()
        self.assertEqual(blocks.attributes, [b])
        self.assertEqual(len(blocks.columns), 1)
        np.testing.assert_equal(blocks.columns[0], np.arange(5))
        self.assertEqual(
            {k: list(v) for k, v in blocks.indices.items()},
            {(0, 0): [0, 1, 2, 4], (1, 0): [5], (2, 0): [3, 6, 9],
             (3, 0): [7], (4, 0): [8]})

        self.change_x(index_of(c))  # c
        self.change_r(0)
        for width2_idx, binning in enumerate(widget.x_binner.binnings):
            if binning.width == 2:
                break
        else:
            assert False

        widget.x_binner.bin_index = width2_idx
        blocks = widget.compute_block_data()
        self.assertEqual(len(blocks.attributes[0].values), 10)
        self.assertEqual(len(blocks.columns), 1)
        np.testing.assert_equal(blocks.columns[0], np.arange(10))
        self.assertEqual(
            {k: list(v) for k, v in blocks.indices.items()},
            {(0, 0): [0], (1, 0): [1, 2], (2, 0): [3, 4], (3, 0): [5, 6],
             (4, 0): [7, 8],
             (5, 0): [], (6, 0): [], (7, 0): [], (8, 0): [], (9, 0): [9]})

        self.change_x(3)  # day of week
        self.change_r(0)
        blocks = widget.compute_block_data()
        self.assertEqual(len(blocks.attributes[0].values), 7)
        self.assertEqual(len(blocks.columns), 1)
        np.testing.assert_equal(blocks.columns[0], np.arange(7))
        self.assertEqual(
            {k: list(v) for k, v in blocks.indices.items()},
            {(0, 0): [4], (1, 0): [5], (2, 0): [6],
             (3, 0): [0, 7], (4, 0): [1, 8], (5, 0): [2],
             (6, 0): [3, 9]})

        self.change_r(3)  # c
        widget.r_binner.bin_index = width2_idx
        blocks = widget.compute_block_data()
        self.assertEqual(len(blocks.attributes), 2)
        self.assertEqual(len(blocks.attributes[0].values), 7)
        self.assertEqual(len(blocks.attributes[1].values), 10)
        self.assertEqual(len(blocks.columns), 2)
        np.testing.assert_equal(blocks.columns[0], np.repeat(np.arange(7), 10))
        np.testing.assert_equal(blocks.columns[1], list(range(10)) * 7)
        indices = {(x, r): [] for x in range(7) for r in range(10)}
        indices.update(
            {(0, 2): [4], (1, 3): [5], (2, 3): [6], (3, 0): [0], (3, 4): [7],
             (4, 1): [1], (4, 4): [8], (5, 1): [2], (6, 2): [3], (6, 9): [9]})
        self.assertEqual(
            {k: list(v) for k, v in blocks.indices.items()}, indices)

        widget.r_binner.bin_index = len(widget.r_binner.binnings) - 1
        blocks = widget.compute_block_data()
        self.assertEqual(len(blocks.attributes[1].values), 2)
        self.assertEqual(len(blocks.columns), 2)
        np.testing.assert_equal(blocks.columns[0], np.repeat(np.arange(7), 2))
        np.testing.assert_equal(blocks.columns[1], list(range(2)) * 7)
        self.assertEqual(
            {k: list(v) for k, v in blocks.indices.items()},
            {(0, 0): [4], (0, 1): [],
             (1, 0): [5], (1, 1): [],
             (2, 0): [6],  (2, 1): [],
             (3, 0): [0, 7], (3, 1): [],
             (4, 0): [1, 8], (4, 1): [],
             (5, 0): [2], (5, 1): [],
             (6, 0): [3], (6, 1): [9]}
        )

        self.change_r(1)  # a
        blocks = widget.compute_block_data()
        self.assertEqual(len(blocks.attributes), 2)
        self.assertEqual(len(blocks.attributes[0].values), 7)
        self.assertEqual(len(blocks.attributes[1].values), 3)
        self.assertEqual(len(blocks.columns), 2)
        np.testing.assert_equal(blocks.columns[0], np.repeat(np.arange(7), 3))
        np.testing.assert_equal(blocks.columns[1], list(range(3)) * 7)
        indices = {(x, r): [] for x in range(7) for r in range(3)}
        indices.update(
            {(0, 1): [4], (1, 1): [5], (2, 1): [6], (3, 0): [0], (3, 1): [7],
             (4, 0): [1], (4, 1): [8], (5, 0): [2], (6, 0): [3], (6, 2): [9]})
        self.assertEqual(
            {k: list(v) for k, v in blocks.indices.items()}, indices)

    def test_compute_data(self):
        widget = self.widget
        self.send_signal(widget.Inputs.time_series, self.time_data)
        a, b, c, d, *_ = self.data.domain.attributes
        c_column = self.data.get_column(c)
        c.number_of_decimals = 8

        columns = [np.repeat(np.arange(3), 5), np.array(list(range(5)) * 3)]
        indices = {(x, r): np.array([]) for x in range(3) for r in range(5)}
        indices[(0, 0)] = np.arange(6)
        indices[(2, 1)] = np.arange(6, 10)
        widget.block_data = BlockData([a, b], columns, indices)

        counts = np.zeros(len(columns[0]))
        counts[0] = 6
        counts[2 * 5 + 1] = 4

        self.change_color(0)  # None
        data = widget.compute_data()
        self.assertEqual(len(data.domain.attributes), 3)
        self.assertEqual(data.domain.attributes[:2], (a, b))
        self.assertIsInstance(data.domain.attributes[2], ContinuousVariable)
        np.testing.assert_equal(data.get_column(0), [0, 2])
        np.testing.assert_equal(data.get_column(1), [0, 1])
        np.testing.assert_equal(data.get_column(2), [6, 4])

        self.change_color(3)  # c
        widget.aggregation = "Mean value"
        data = widget.compute_data()
        self.assertEqual(len(data.domain.attributes), 3)
        self.assertEqual(data.domain.attributes[:2], (a, b))
        self.assertIsInstance(data.domain.attributes[2], ContinuousVariable)
        self.assertEqual(data.domain.class_var.name, "c (mean)")
        # clones old variable, but with new name
        self.assertEqual(data.domain.class_var.number_of_decimals, 8)
        np.testing.assert_equal(data.get_column(0), [0, 2])
        np.testing.assert_equal(data.get_column(1), [0, 1])
        np.testing.assert_equal(data.get_column(2), [6, 4])
        means = np.full(len(data), np.nan)
        means[0] = np.mean(c_column[:6])
        means[1] = np.mean(c_column[6:])
        np.testing.assert_equal(data.Y, means)

        widget.aggregation = "Variance"
        data = widget.compute_data()
        self.assertEqual(data.domain.class_var.name, "c (var)")
        # new variable
        self.assertEqual(data.domain.class_var.number_of_decimals, 3)
        vars_ = np.full(len(data), np.nan)
        vars_[0] = np.var(c_column[:6])
        vars_[1] = np.var(c_column[6:])
        np.testing.assert_equal(data.Y, vars_)

    def test_context_no_timeseries(self):
        # Context handler should not match context with time period if data
        # is not TimeSeries
        widget = self.widget

        self.send_signal(widget.Inputs.time_series, self.time_data)
        self.send_signal(widget.Inputs.time_series, self.data)
        self.assertNotIsInstance(widget.x_var, str)


if __name__ == "__main__":
    unittest.main()
