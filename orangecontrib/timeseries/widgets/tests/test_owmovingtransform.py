import sys
import unittest
from unittest.mock import Mock

import numpy as np
from AnyQt.QtCore import Qt, QItemSelectionModel
from AnyQt.QtWidgets import QCheckBox

from Orange.data import DiscreteVariable, ContinuousVariable, Domain, \
    TimeVariable
from Orange.widgets.tests.base import WidgetTest
from orangewidget.tests.base import GuiTest
from orangecontrib.timeseries import Timeseries

from orangecontrib.timeseries.widgets.owmovingtransform import \
    OWMovingTransform, TransformationsModel, NumericFilterProxy


class TransformationsModelTest(GuiTest):
    def setUp(self) -> None:
        d1, d2 = (DiscreteVariable(n, values=("a", "b")) for n in ("d1", "d2"))
        c1, c2 = (ContinuousVariable(n) for n in ("c1", "c2"))
        self.model = TransformationsModel()
        self.model.set_variables([d1, d2, c1, c2])

    def test_transformationsmodel(self):
        model = self.model
        index = model.index

        for i in range(4):
            self.assertEqual(model.get_transformations(index(i)), [])

        model.set_transformations(index(0), {"mode", "mean", "std"})
        model.set_transformations(1, {"min", "max"})
        model.set_transformation([index(1), index(2)], "min", True)
        model.set_transformation([index(1), index(2)], "span", True)
        model.set_transformation([index(0), index(1)], "std", False)

        self.assertEqual(model.get_transformations(0), ["mean", "mode"])
        self.assertEqual(model.get_transformations(index(1)), ["min", "max", "span"])
        self.assertEqual(model.get_transformations(2), ["min", "span"])
        self.assertEqual(model.get_transformations(3), [])

        self.assertTrue(model.data(index(0), Qt.FontRole).bold())
        self.assertIsNone(model.data(index(3), Qt.FontRole))

        self.assertEqual(model.data(index(0)), "d1: mean, mode")
        self.assertEqual(model.data(index(1)), "d2: min, max, span")
        self.assertEqual(model.data(index(2)), "c1: min, span")
        self.assertEqual(model.data(index(3)), "c2")

        model.set_variables(model[:])
        self.assertEqual(model.get_transformations(index(i)), [])

    def test_filter(self):
        proxy = NumericFilterProxy(self.model, False)
        self.assertEqual(proxy.rowCount(), 4)
        self.assertEqual([proxy.data(proxy.index(i, 0)) for i in range(4)],
                         "d1 d2 c1 c2".split())

        proxy.set_pattern("1")
        self.assertEqual(proxy.rowCount(), 2)
        self.assertEqual([proxy.data(proxy.index(i, 0)) for i in range(2)],
                         "d1 c1".split())

        proxy.set_filtering_numeric(True)
        self.assertEqual(proxy.rowCount(), 1)
        self.assertEqual(proxy.data(proxy.index(0, 0)), "c1")

        proxy.set_pattern("")
        self.assertEqual(proxy.rowCount(), 2)
        self.assertEqual([proxy.data(proxy.index(i, 0)) for i in range(2)],
                         "c1 c2".split())

        proxy.set_filtering_numeric(False)
        self.assertEqual(proxy.rowCount(), 4)
        self.assertEqual([proxy.data(proxy.index(i, 0)) for i in range(4)],
                         "d1 d2 c1 c2".split())


class TestOWMovingTransform(WidgetTest):
    def setUp(self):
        self.widget: OWMovingTransform = self.create_widget(OWMovingTransform)
        d1, d2 = (DiscreteVariable(n, values=("a", "b")) for n in ("d1", "d2"))
        c1, c2 = (ContinuousVariable(n) for n in ("c1", "c2"))
        domain = Domain([d1, c1, c2], d2)
        self.time_data = Timeseries.from_numpy(
            domain,
            [[0, 1, 2.5],
             [0, 2, 0],
             [0, 2.5, np.nan],
             [0, 2.75, 1],
             [1, 3, -1],
             [1, 3.5, -2]],
            [0, 1, np.nan, 1, 0, 0],
            time_attr=c1
        )

        self.data = Timeseries.from_numpy(
            domain,
            [[0, 1, 2.5],
             [0, 2.5, 0],
             [0, 4, np.nan],
             [0, 2.75, 1],
             [1, 3, -1],
             [1, 3.5, -2]],
            [0, 1, np.nan, 1, 0, 0],
        )

    if sys.platform == "win32":
        def test_minimum_size(self):
            # The middle section (list view, line edit, checkbox) appears to
            # be too wide (not observed in practice, but discovered by hiding it
            pass

    def test_set_data_model(self):
        widget = self.widget
        domain = self.data.domain

        self.send_signal(widget.Inputs.time_series, self.data)
        self.assertEqual(
            tuple(widget.var_model),
            domain.attributes + domain.class_vars + domain.metas[1:])
        self.assertFalse(widget.rb_period.isEnabled())
        self.assertFalse(widget.controls.period_width.isEnabled())

        self.send_signal(widget.Inputs.time_series, self.time_data)
        self.assertEqual(
            tuple(widget.var_model),
            (domain.attributes[0], domain.attributes[2])
            + domain.class_vars + domain.metas[1:])
        self.assertTrue(widget.rb_period.isEnabled())
        self.assertTrue(widget.controls.period_width.isEnabled())

        self.send_signal(widget.Inputs.time_series, None)
        self.assertEqual(widget.var_model.rowCount(), 0)
        self.assertTrue(widget.rb_period.isEnabled())
        self.assertTrue(widget.controls.period_width.isEnabled())

        # TODO: Test selection_changed and set_naming_visibility

    def test_filter_pattern(self):
        widget = self.widget
        self.assertTrue(widget.clear_filter.isHidden())

        self.send_signal(widget.Inputs.time_series, self.data)
        self.assertTrue(widget.clear_filter.isHidden())

        widget.filter_line.setText("2")
        widget.filter_line.textEdited.emit("2")
        self.assertFalse(widget.clear_filter.isHidden())
        self.assertEqual(widget.var_view.model().rowCount(), 2)

        widget.filter_line.setText("c2")
        widget.filter_line.textEdited.emit("c2")
        self.assertFalse(widget.clear_filter.isHidden())
        self.assertEqual(widget.var_view.model().rowCount(), 1)
        self.assertEqual(widget.var_view.model().index(0, 0).data(), "c2")

        widget.filter_line.setText("c4")
        widget.filter_line.textEdited.emit("c4")
        self.assertFalse(widget.clear_filter.isHidden())
        self.assertEqual(widget.var_view.model().rowCount(), 0)

        widget.filter_line.setText("c2")
        widget.filter_line.textEdited.emit("c2")
        self.assertFalse(widget.clear_filter.isHidden())
        self.assertEqual(widget.var_view.model().rowCount(), 1)
        self.assertEqual(widget.var_view.model().index(0, 0).data(), "c2")

        widget.clear_filter.click()
        self.assertTrue(widget.clear_filter.isHidden())
        self.assertEqual(widget.var_view.model().rowCount(), 4)

        widget.filter_line.setText("c2")
        widget.filter_line.textEdited.emit("c2")
        self.assertFalse(widget.clear_filter.isHidden())
        self.assertEqual(widget.var_view.model().rowCount(), 1)
        self.assertEqual(widget.var_view.model().index(0, 0).data(), "c2")

        widget.filter_line.setText("")
        widget.filter_line.textEdited.emit("")
        self.assertTrue(widget.clear_filter.isHidden())
        self.assertEqual(widget.var_view.model().rowCount(), 4)

    def test_filter_numeric(self):
        widget = self.widget
        model = widget.var_view.model()
        widget.only_numeric = False

        self.send_signal(widget.Inputs.time_series, self.data)

        self.assertEqual(model.rowCount(), 4)

        widget.controls.only_numeric.click()
        self.assertEqual(model.rowCount(), 2)
        self.assertEqual(model.index(0, 0).data(), "c1")
        self.assertEqual(model.index(1, 0).data(), "c2")

    def test_selection_on_filtered(self):
        widget = self.widget
        model = widget.var_view.model()

        selmodel = widget.var_view.selectionModel()
        widget.only_numeric = False
        widget.controls.only_numeric.click()

        self.send_signal(widget.Inputs.time_series, self.data)
        assert model.rowCount() == 2

        selmodel.select(model.index(0, 0), QItemSelectionModel.Select)
        selmodel.select(model.index(1, 0), QItemSelectionModel.Select)

        self.assertEqual({index.row() for index in widget._current_selection()},
                         {1, 2})

    def test_checkbox_changing(self):
        # If this test fails, and test_selection_on_filtered fails too,
        # first fix test_selection_on_filtered
        widget = self.widget
        model = widget.var_view.model()
        varmodel = widget.var_model

        selmodel = widget.var_view.selectionModel()
        widget.only_numeric = False
        widget.controls.only_numeric.click()

        self.send_signal(widget.Inputs.time_series, self.data)
        assert model.rowCount() == 2

        self.assertEqual(widget.var_hints, {})

        selmodel.select(model.index(1, 0), QItemSelectionModel.Select) # 2 (c2)

        widget.findChild(QCheckBox, "mean").click()
        self.assertEqual(varmodel.get_transformations(2), ["mean"])
        self.assertEqual(widget.var_hints, {("c2", True): {"mean"}})

        selmodel.select(model.index(0, 0), QItemSelectionModel.Select) # 2 (c2)

        widget.findChild(QCheckBox, "max").click()
        self.assertEqual(varmodel.get_transformations(1), ["max"])
        self.assertEqual(varmodel.get_transformations(2), ["mean", "max"])
        self.assertEqual(widget.var_hints, {("c1", True): {"max"}, ("c2", True): {"mean", "max"}})

        widget.findChild(QCheckBox, "max").click()
        self.assertEqual(varmodel.get_transformations(1), [])
        self.assertEqual(varmodel.get_transformations(2), ["mean"])
        self.assertEqual(widget.var_hints, {("c2", True): {"mean"}})

    def test_checkbox_states(self):
        # If this test fails, first check test_selection_on_filtered
        widget = self.widget
        model = widget.var_view.model()

        selmodel = widget.var_view.selectionModel()
        widget.only_numeric = False

        self.send_signal(widget.Inputs.time_series, self.data)

        maxbox = widget.findChild(QCheckBox, "max")
        meanbox = widget.findChild(QCheckBox, "mean")
        modebox = widget.findChild(QCheckBox, "mode")

        self.assertFalse(maxbox.isEnabled())
        self.assertFalse(meanbox.isEnabled())
        self.assertFalse(modebox.isEnabled())

        selmodel.select(model.index(1, 0), QItemSelectionModel.Select)  # c1
        self.assertTrue(maxbox.isEnabled())
        self.assertTrue(meanbox.isEnabled())
        self.assertTrue(modebox.isEnabled())

        maxbox.click()
        meanbox.click()

        selmodel.select(model.index(2, 0), QItemSelectionModel.Select)  # c2
        self.assertEqual(maxbox.checkState(), Qt.PartiallyChecked)
        self.assertEqual(meanbox.checkState(), Qt.PartiallyChecked)

        maxbox.click()
        self.assertEqual(maxbox.checkState(), Qt.Checked)
        self.assertEqual(meanbox.checkState(), Qt.PartiallyChecked)

        selmodel.select(model.index(0, 0), QItemSelectionModel.Select)  # d1
        self.assertFalse(maxbox.isEnabled())
        self.assertFalse(meanbox.isEnabled())
        self.assertTrue(modebox.isEnabled())

    def test_set_data_applies_hints(self):
        widget = self.widget
        widget.commit.now = Mock()
        varmodel = widget.var_model
        widget.var_hints = {("d1", False): {"mode"},
                            ("c1", True): {"min", "max"},
                            ("c2", False): {"mode"},
                            ("foo", True): {"var"}}

        self.send_signal(widget.Inputs.time_series, self.data)

        self.assertEqual(varmodel.get_transformations(0), ["mode"])
        self.assertEqual(varmodel.get_transformations(1), ["min", "max"])

    def test_compute_sliding_window(self):
        # if this failes, first check test_set_data_applies_hints
        widget = self.widget
        widget.commit.now = Mock()
        widget.var_hints = {("d2", False): {"mode"},
                            ("c1", True): {"min", "max"},
                            ("c2", False): {"mode"},
                            ("foo", True): {"var"}}
        widget.method = widget.SlidingWindow
        widget.window_width = 3

        self.send_signal(widget.Inputs.time_series, self.data)

        widget.keep_instances = widget.DiscardOriginal
        data = widget._compute_sliding_window()
        self.assertEqual([attr.name for attr in data.domain.attributes],
                         ['c1 (min)', 'c1 (max)', 'd2 (mode)'])
        self.assertEqual(data.domain.class_vars, ())
        self.assertEqual(data.domain.metas, ())
        np.testing.assert_equal(
            data.X,
            [[1, 4, 0],
             [2.5, 4, 1],
             [2.75, 4, 0],
             [2.75, 3.5, 0]]
            )

        widget.keep_instances = widget.KeepComplete
        data = widget._compute_sliding_window()
        self.assertEqual([attr.name for attr in data.domain.attributes],
                         ['d1', 'c1', 'c1 (min)', 'c1 (max)', 'c2', 'd2 (mode)'])
        self.assertIs(data.domain.class_var, self.data.domain.class_var)
        self.assertEqual(data.domain.metas, ())
        np.testing.assert_equal(
            data.X,
            [[0.0, 4.0, 1.0, 4.0, np.nan, 0.0],
             [0.0, 2.75, 2.5, 4.0, 1.0, 1.0],
             [1.0, 3.0, 2.75, 4.0, -1.0, 0.0],
             [1.0, 3.5, 2.75, 3.5, -2.0, 0.0]]
        )
        np.testing.assert_equal(data.Y, self.data.Y[2:])

        widget.keep_instances = widget.KeepAll
        data = widget._compute_sliding_window()
        self.assertEqual([attr.name for attr in data.domain.attributes],
                         ['d1', 'c1', 'c1 (min)', 'c1 (max)', 'c2', 'd2 (mode)'])
        self.assertIs(data.domain.class_var, self.data.domain.class_var)
        self.assertEqual(data.domain.metas, ())
        np.testing.assert_equal(
            data.X,
            [[0.0, 1.0, np.nan, np.nan, 2.5, np.nan],
             [0.0, 2.5, np.nan, np.nan, 0.0, np.nan],
             [0.0, 4.0, 1.0, 4.0, np.nan, 0.0],
             [0.0, 2.75, 2.5, 4.0, 1.0, 1.0],
             [1.0, 3.0, 2.75, 4.0, -1.0, 0.0],
             [1.0, 3.5, 2.75, 3.5, -2.0, 0.0]]
        )
        np.testing.assert_equal(data.Y, self.data.Y)

    def test_compute_sliding_window_cumulative_all(self):
        # if this failes, first check test_set_data_applies_hints
        # and test_compute_sliding_window
        widget = self.widget
        widget.commit.now = Mock()
        widget.var_hints = {("c1", True): {"cumsum"}}
        widget.method = widget.SlidingWindow
        widget.window_width = 3

        self.send_signal(widget.Inputs.time_series, self.data)
        widget.keep_instances = widget.KeepAll
        data = widget._compute_sliding_window()
        np.testing.assert_equal(
            data.X,
            [[0.0, 1.0, 1.0, 2.5],
             [0.0, 2.5, 3.5, 0.0],
             [0.0, 4.0, 7.5, np.nan],
             [0.0, 2.75, 10.25, 1.0],
             [1.0, 3.0, 13.25, -1.0],
             [1.0, 3.5, 16.75, -2.0]])

    def test_compute_sliding_window_warnings(self):
        widget = self.widget
        widget.commit.now = Mock()
        widget.window_width = 5
        widget.method = widget.SlidingWindow
        widget.keep_instances = widget.DiscardOriginal

        self.send_signal(widget.Inputs.time_series, self.data)
        self.assertIsNone(widget._compute_sliding_window())
        self.assertTrue(widget.Warning.no_aggregations.is_shown())

        self.send_signal(widget.Inputs.time_series, self.data[:4])
        widget._compute_sliding_window()
        self.assertTrue(widget.Warning.window_to_large.is_shown())

    def test_compute_sequential_blocks(self):
        # if this failes, first check test_set_data_applies_hints
        widget = self.widget
        widget.commit.now = Mock()
        widget.var_hints = {("d2", False): {"mode"},
                            ("c1", True): {"min", "max", "cumsum"},
                            ("c2", False): {"mode"},
                            ("foo", True): {"var"}}
        widget.method = widget.SequentialBlocks
        widget.block_width = 3

        self.send_signal(widget.Inputs.time_series, self.data)

        widget.ref_instance = widget.DiscardOriginal
        data = widget._compute_sequential_blocks()
        self.assertEqual([attr.name for attr in data.domain.attributes],
                         ['c1 (min)', 'c1 (max)', 'd2 (mode)'])
        self.assertEqual(data.domain.class_vars, ())
        self.assertEqual(data.domain.metas, ())
        np.testing.assert_equal(
            data.X,
            [[1, 4, 0],
             [2.75, 3.5, 0]]
            )

        widget.ref_instance = widget.KeepFirst
        data = widget._compute_sequential_blocks()
        self.assertEqual([attr.name for attr in data.domain.attributes],
                         ['d1', 'c1', 'c1 (min)', 'c1 (max)', 'c2', 'd2 (mode)'])
        self.assertIs(data.domain.class_var, self.data.domain.class_var)
        self.assertEqual(data.domain.metas, ())
        np.testing.assert_equal(
            data.X,
            [[0, 1, 1, 4, 2.5, 0],
             [0, 2.75, 2.75, 3.5, 1, 0]]
        )
        np.testing.assert_equal(data.Y, [0, 1])

        widget.ref_instance = widget.KeepMiddle
        data = widget._compute_sequential_blocks()
        self.assertEqual([attr.name for attr in data.domain.attributes],
                         ['d1', 'c1', 'c1 (min)', 'c1 (max)', 'c2', 'd2 (mode)'])
        self.assertIs(data.domain.class_var, self.data.domain.class_var)
        self.assertEqual(data.domain.metas, ())
        np.testing.assert_equal(
            data.X,
            [[0, 2.5, 1, 4, 0, 0],
             [1, 3, 2.75, 3.5, -1, 0]]
        )
        np.testing.assert_equal(data.Y, [1, 0])

        widget.ref_instance = widget.KeepLast
        data = widget._compute_sequential_blocks()
        self.assertEqual([attr.name for attr in data.domain.attributes],
                         ['d1', 'c1', 'c1 (min)', 'c1 (max)', 'c2', 'd2 (mode)'])
        self.assertIs(data.domain.class_var, self.data.domain.class_var)
        self.assertEqual(data.domain.metas, ())
        np.testing.assert_equal(
            data.X,
            [[0, 4, 1, 4, np.nan, 0],
             [1, 3.5, 2.75, 3.5, -2, 0]]
        )
        np.testing.assert_equal(data.Y, [np.nan, 0])

    def test_compute_sequential_blocks_even_and_large(self):
        # if this failes, first check test_set_data_applies_hints
        widget = self.widget
        widget.commit.now = Mock()
        widget.var_hints = {("d2", False): {"mode"},
                            ("c1", True): {"min", "max", "cumsum"},
                            ("c2", False): {"mode"},
                            ("foo", True): {"var"}}
        widget.method = widget.SequentialBlocks
        widget.block_width = 4

        self.send_signal(widget.Inputs.time_series, self.data)

        widget.method = widget.SequentialBlocks

        widget.ref_instance = widget.DiscardOriginal
        data = widget._compute_sequential_blocks()
        self.assertEqual([attr.name for attr in data.domain.attributes],
                         ['c1 (min)', 'c1 (max)', 'd2 (mode)'])
        self.assertEqual(data.domain.class_vars, ())
        self.assertEqual(data.domain.metas, ())
        np.testing.assert_equal(data.X, [[1, 4, 1]])

        widget.ref_instance = widget.KeepFirst
        data = widget._compute_sequential_blocks()
        self.assertEqual([attr.name for attr in data.domain.attributes],
                         ['d1', 'c1', 'c1 (min)', 'c1 (max)', 'c2', 'd2 (mode)'])
        self.assertIs(data.domain.class_var, self.data.domain.class_var)
        self.assertEqual(data.domain.metas, ())
        np.testing.assert_equal(data.X, [[0, 1, 1, 4, 2.5, 1]])
        np.testing.assert_equal(data.Y, [0])

        widget.ref_instance = widget.KeepMiddle
        data = widget._compute_sequential_blocks()
        self.assertEqual([attr.name for attr in data.domain.attributes],
                         ['d1', 'c1', 'c1 (min)', 'c1 (max)', 'c2', 'd2 (mode)'])
        self.assertIs(data.domain.class_var, self.data.domain.class_var)
        self.assertEqual(data.domain.metas, ())
        np.testing.assert_equal(data.X, [[0, 4, 1, 4, np.nan, 1]])
        np.testing.assert_equal(data.Y, [np.nan])

        widget.ref_instance = widget.KeepLast
        data = widget._compute_sequential_blocks()
        self.assertEqual([attr.name for attr in data.domain.attributes],
                         ['d1', 'c1', 'c1 (min)', 'c1 (max)', 'c2', 'd2 (mode)'])
        self.assertIs(data.domain.class_var, self.data.domain.class_var)
        self.assertEqual(data.domain.metas, ())
        np.testing.assert_equal(data.X, [[0, 2.75, 1, 4, 1, 1]])
        np.testing.assert_equal(data.Y, [1])

    def test_compute_sequential_blocks_warnings(self):
        widget = self.widget
        widget.block_width = 5
        widget.method = widget.SequentialBlocks
        widget.keep_instances = widget.DiscardOriginal

        self.send_signal(widget.Inputs.time_series, self.data)
        self.assertIsNone(widget._compute_sequential_blocks())
        self.assertTrue(widget.Warning.no_aggregations.is_shown())

        self.send_signal(widget.Inputs.time_series, self.data[:4])
        self.assertIsNone(self.get_output(widget.Outputs.time_series))
        self.assertTrue(widget.Warning.block_to_large.is_shown())

        widget.Warning.clear()

        widget.var_hints = {("c1", True): {"cumsum"},
                            ("c2", False): {"cumsum", "cumprod"}}
        self.send_signal(widget.Inputs.time_series, self.data)
        self.assertTrue(widget.Warning.no_aggregations.is_shown())
        self.assertTrue(widget.Warning.inapplicable_aggregations.is_shown())

    def test_period_aggregation(self):
        widget = self.widget
        widget.block_width = 5
        widget.method = widget.TimePeriods
        widget.var_hints = {("x", True): {"mean", "cumsum"}}
        time = TimeVariable("t")
        domain = Domain([time], ContinuousVariable("x"))
        column = [3, 4, 5, 6,
                  1, 2,
                  np.nan, 13, 15,
                  np.nan]

        timess = [("Years", ["1971-01-01", "1971-01-26", "1971-06-05", "1971-12-31T23:59:59",
                             "1972-01-01", "1972-12-31",
                             "1974-05-02", "1974-02-04", "1974-07-03",
                             "1989-07-31"],
                             ["1971", "1972", "1974", "1989"]),
                  ("Months", ["1998-01-01", "1998-01-26", "1998-01-27", "1998-01-28",
                              "1998-08-01", "1998-08-31",
                              "1999-05-02", "1999-05-04", "1999-05-10",
                              "2000-07-31"],
                              ["1998-01", "1998-08", "1999-05", "2000-07"]),
                  ("Days", ["1998-01-01T06:18:00", "1998-01-01T09:12:13", "1998-01-01T09:44:12", "1998-01-01T23:59:59",
                              "1998-01-02T00:00:00", "1998-01-02T15:12:11",
                              "1999-05-02T12:15:17", "1999-05-02T12:12:12", "1999-05-02T06:01:02",
                              "2000-07-31T00:00:00"],
                              ["1998-01-01", "1998-01-02", "1999-05-02", "2000-07-31"]),
                  ("Hours", ["1998-01-01T06:18:00", "1998-01-01T06:12:13", "1998-01-01T06:44:12", "1998-01-01T06:59:59",
                              "1998-01-01T07:00:00", "1998-01-01T07:12:11",
                              "1999-05-02T07:15:17", "1999-05-02T07:12:12", "1999-05-02T07:01:02",
                              "2000-07-31T00:00:00"],
                              ["1998-01-01T06:00:00", "1998-01-01T07:00:00", "1999-05-02T07:00:00", "2000-07-31T00:00:00"]),
                  ("Minutes", ["1998-01-01T06:18:00", "1998-01-01T06:18:13", "1998-01-01T06:18:12", "1998-01-01T06:18:59",
                              "1998-01-01T06:19:00", "1998-01-01T06:19:11",
                              "1999-05-02T07:21:17", "1999-05-02T07:21:12", "1999-05-02T07:21:02",
                              "2000-07-31T00:00:00"],
                              ["1998-01-01T06:18:00", "1998-01-01T06:19:00", "1999-05-02T07:21:00", "2000-07-31T00:00:00"]),
                  ("Seconds", ["06:18:58.12", "06:18:58.14", "06:18:58.23", "06:18:58.99",
                               "06:18:59", "06:18:59.02",
                               "06:19:00", "06:19:00.4", "06:19:00.4",
                               "09:00:00"],
                              ["06:18:58", "06:18:59", "06:19", "09:00"]),
                  ("Month of year", ["1972-04-02", "1989-04-11", "1972-04-02", "1972-04-30",
                                     "1972-05-01", "1921-05-02",
                                     "1931-09-01", "1931-09-30", "1938-09-12",
                                     "2000-12-31"],
                                    [4, 5, 9, 12]),
                  ("Day of year", ["1970-01-05", "1989-01-05", "1970-01-05", "1901-01-05",
                                   "1972-01-06", "1973-01-06",
                                   "1931-03-02", "1932-03-01", "1938-03-02", # leap years
                                   "2000-05-01"],
                                    [5, 6, 1 + 30 + 28 + 2, 122]),
                  ("Day of month", ["1970-01-05", "1989-03-05", "1970-06-05", "1901-12-05",
                                   "1972-01-06", "1973-10-06",
                                   "1931-03-12", "1932-03-12", "1938-04-12",
                                   "2000-05-31"],
                                    [5, 6, 12, 31]),
                  ("Day of week", ["2022-06-07", "2022-05-24", "2018-02-20", "2022-06-07",
                                   "2018-09-06", "2016-02-11",
                                   "2016-02-12", "2016-02-19", "2022-06-10",
                                   "2000-06-11"],
                                    [1, 3, 4, 6]),
                  ("Hour of day", ["2022-06-07T03:12:14", "03:16", "03:50", "03:59",
                                   "2018-09-06T05:12:12", "2016-02-11T05:11:00",
                                   "2016-02-12T12:15:17", "2016-02-19T12:34:12", "2022-06-10T12:00:00",
                                   "2000-06-11T18:22:12"],
                                    [3, 5, 12, 18]),
                  ]
        widget.use_names = False
        for widget.period_width, dates, periods in timess:
            x = [[time.to_val(x)] for x in dates]
            data = Timeseries.from_numpy(domain, x, column, time_attr=time)
            self.send_signal(widget.Inputs.time_series, data)
            out = self.get_output(widget.Outputs.time_series)
            self.assertEqual(len(out.domain.attributes), 3)
            self.assertEqual(out.domain.class_vars, ())
            np.testing.assert_equal(out.X[:, 1], [4, 2, 3, 1])
            np.testing.assert_equal(out.X[:, 2], [4.5, 1.5, 14, np.nan])
            if " of " in widget.period_width:
                np.testing.assert_equal(out.X[:, 0], periods)
                if widget.period_width in ("Month of year", "Day of week"):
                    self.assertIsInstance(out.domain.attributes[0], ContinuousVariable)
                    widget.use_names = True
                    widget.commit.now()
                    out = self.get_output(widget.Outputs.time_series)
                    np.testing.assert_equal(
                        out.X[:, 0] + (widget.period_width == "Month of year"),
                        periods)
                    self.assertIsInstance(out.domain.attributes[0], DiscreteVariable)
                    widget.use_names = False
            else:
                np.testing.assert_equal(out.X[:, 0],
                                        [time.to_val(x) for x in periods])

        widget.var_hints = {("x", True): {"mean", "cumsum"}}
        self.send_signal(widget.Inputs.time_series, data)
        self.assertTrue(widget.Warning.inapplicable_aggregations.is_shown())

        widget.var_hints = {("x", True): {"mean"}}
        self.send_signal(widget.Inputs.time_series, data)
        self.assertFalse(widget.Warning.inapplicable_aggregations.is_shown())

    def test_report(self):
        widget = self.widget
        widget.commit.now = Mock()
        widget.var_hints = {("d1", False): {"mode"},
                            ("c1", True): {"min", "max"},
                            ("c2", False): {"mode"},
                            ("foo", True): {"var"}}

        self.send_signal(widget.Inputs.time_series, self.data)
        for widget.method in (widget.SlidingWindow,
                              widget.SequentialBlocks,
                              widget.TimePeriods):
            widget.send_report()

    def test_migrated_aggregate_settings(self):
        settings = {'agg_interval': 'day', 'autocommit': False,
                    'controlAreaVisible': True,
                    'savedWidgetGeometry': None,
                    '__version__': 1, 'context_settings': []}
        widget = self.create_widget(OWMovingTransform, stored_settings=settings)
        self.send_signal(widget.Inputs.time_series, self.data)
        self.assertTrue(widget.Error.migrated_aggregate.is_shown())
        widget.controls.method.buttons[0].click()
        widget.controls.method.buttons[1].click()
        self.assertFalse(widget.Error.migrated_aggregate.is_shown())


if __name__ == "__main__":
    unittest.main()
