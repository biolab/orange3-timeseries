from itertools import chain
from datetime import datetime, timezone
from copy import deepcopy
import unittest
from unittest.mock import patch, Mock

import numpy as np
import scipy.sparse as sp

from AnyQt.QtWidgets import QLineEdit
from AnyQt.QtCore import Qt, QPointF, QPoint
from AnyQt.QtGui import QMouseEvent

from Orange.data import \
    Table, Domain, DiscreteVariable, ContinuousVariable, TimeVariable
from Orange.widgets.tests.base import WidgetTest

from orangecontrib.timeseries.functions import timestamp
from orangecontrib.timeseries.widgets.owtabletotimeseries import \
    OWTableToTimeseries, LineEdit
from orangewidget.settings import Context


class TestAsTimeSeriesWidgetBase(WidgetTest):
    def setUp(self):
        self.widget: OWTableToTimeseries = self.create_widget(OWTableToTimeseries)

        x, y, m = (ContinuousVariable(n) for n in "xym")
        domain = Domain(
            [DiscreteVariable("a", values=tuple("abc")), x, y],
            DiscreteVariable("c", values=tuple("ab")),
            [m,
             TimeVariable("t", have_time=True),
             TimeVariable("u", have_date=True, have_time=True)])
        self.data = Table.from_numpy(
            domain,
            np.array([[0, 1, 0],
                      [2, 0, np.nan],
                      [0, -1, 2],
                      [np.nan, 3.1, 2.7]]),
            np.array([0, 1, np.nan, 0]),
            np.array([[0, 2, 1667471775.0],  # 2022-11-03 10:36:15
                      [3, np.nan, -1613826000.0],  # 1918-11-11 11:00
                      [np.nan, 3600, np.nan],
                      [1.18, 1805, 677808000.0]  # 1991-06-25
                      ])
        )


# Old tests, which are unspecific but can still catch something
class TestAsTimeSeriesWidgetOld(TestAsTimeSeriesWidgetBase):
    def test_basic_output(self):
        w = self.widget
        w.implied_sequence = 0
        self.send_signal(w.Inputs.data, self.data)
        model = w.var_combo.model()
        self.assertEqual(len(model), 6)
        out = self.get_output(w.Outputs.time_series)
        self.assertIs(out.time_variable, self.data.domain.metas[1])
        np.testing.assert_equal(out.time_values, [2, 1805, 3600])

    def test_no_output_when_all_nan(self):
        w = self.widget
        w.implied_sequence = 0
        with self.data.unlocked():
            self.data.metas[:, 1] = np.nan
        self.send_signal(w.Inputs.data, self.data)
        self.assertTrue(w.Warning.nan_times.is_shown())
        self.assertIsNone(self.get_output(w.Outputs.time_series))

    def test_sparse_data(self):
        widget = self.widget
        widget.implied_sequence = 0

        data = self.data
        with data.unlocked():
            data.X = sp.csr_matrix(data.X)
            data.Y = sp.csr_matrix(data.Y)
            data.metas = sp.csr_matrix(data.metas.astype(float))
        self.send_signal(widget.Inputs.data, data)

        widget.attribute = "x"
        widget.commit.now()
        out = self.get_output(widget.Outputs.time_series)
        np.testing.assert_equal(
            out.X,
            [[0, -1, 2], [2, 0, np.nan], [0, 1, 0], [np.nan, 3.1, 2.7]])

        widget.attribute = "y"
        widget.commit.now()
        out = self.get_output(widget.Outputs.time_series)
        np.testing.assert_equal(
            out.X, [[0, 1, 0], [0, -1, 2], [np.nan, 3.1, 2.7]])
        self.assertTrue(widget.Warning.nan_times.is_shown())

        widget.attribute = "m"
        widget.commit.now()
        out = self.get_output(widget.Outputs.time_series)
        np.testing.assert_equal(
            out.X, [[0, 1, 0], [np.nan, 3.1, 2.7], [2, 0, np.nan]])
        self.assertTrue(widget.Warning.nan_times.is_shown())

        widget.attribute = "x"
        widget.commit.now()
        self.assertFalse(widget.Warning.nan_times.is_shown())

        widget.attribute = "m"
        widget.commit.now()
        self.assertTrue(widget.Warning.nan_times.is_shown())

        self.send_signal(widget.Inputs.data, None)
        self.assertFalse(widget.Warning.nan_times.is_shown())


class TestAsTimeSeriesWidget(TestAsTimeSeriesWidgetBase):
    def test_var_model(self):
        w = self.widget
        self.send_signal(w.Inputs.data, self.data)
        self.assertEqual(w.var_combo.model().rowCount(), 6)

        domain = self.data.domain
        c2t2 = Domain(domain.attributes[2:], domain.class_vars, domain.metas)
        self.send_signal(w.Inputs.data, self.data.transform(c2t2))
        self.assertEqual(w.var_combo.model().rowCount(), 5)

        c1t2 = Domain([], domain.class_vars, domain.metas)
        self.send_signal(w.Inputs.data, self.data.transform(c1t2))
        self.assertEqual(w.var_combo.model().rowCount(), 4)

        c0t2 = Domain([], domain.class_vars, domain.metas[1:])
        self.send_signal(w.Inputs.data, self.data.transform(c0t2))
        self.assertEqual(w.var_combo.model().rowCount(), 2)  # no separator

        c2t1 = Domain(domain.attributes, domain.class_vars, domain.metas[2:])
        self.send_signal(w.Inputs.data, self.data.transform(c2t1))
        self.assertEqual(w.var_combo.model().rowCount(), 3)  # no separator

        c2t0 = Domain(domain.attributes, domain.class_vars, [])
        self.send_signal(w.Inputs.data, self.data.transform(c2t0))
        self.assertEqual(w.var_combo.model().rowCount(), 2)  # no separator

    def test_attribute_changed(self):
        w = self.widget
        w.implied_sequence = 1

        self.send_signal(w.Inputs.data, Table("iris"))
        with patch.object(w.commit, 'deferred', wraps=w.commit.deferred) \
                as commit:
            w.var_combo.setCurrentIndex(2)
            w.var_combo.activated.emit(2)
            self.assertEqual(w.implied_sequence, 0)
            self.assertEqual(w.attribute, w.var_combo[2].name)
            commit.assert_called_once()
            self.assertIs(self.get_output(w.Outputs.time_series.time_variable),
                          w.var_combo[2])

    def test_attribute_changed(self):
        w = self.widget
        w.implied_sequence = 1

        self.send_signal(w.Inputs.data, Table("iris"))
        with patch.object(w.commit, 'deferred') as commit:
            w.var_combo.setCurrentIndex(2)
            w.var_combo.activated.emit(2)
            self.assertEqual(w.implied_sequence, 0)
            commit.assert_called_once()

    def test_time_settings_changed_and_update_interface(self):
        w = self.widget

        unit_combo = w.controls.unit
        step_line = w.findChild(LineEdit, "stepline")
        extra_cb = w.controls.include_extra_part
        self.send_signal(w.Inputs.data, Table("iris"))

        with patch.object(w.commit, 'deferred') as commit:
            w.include_extra_part = False

            w.implied_sequence = 0
            w.unit = 0
            unit_combo.textActivated.emit(unit_combo.itemText(0))
            self.assertEqual(w.implied_sequence, 1)
            commit.assert_called_once()
            self.assertFalse(w.datebox.isEnabled())
            self.assertTrue(w.timebox.isEnabled())
            commit.reset_mock()

            w.implied_sequence = 0
            w.unit = 4
            unit_combo.textActivated.emit(unit_combo.itemText(4))
            self.assertEqual(w.implied_sequence, 1)
            commit.assert_called_once()
            self.assertTrue(w.datebox.isEnabled())
            self.assertFalse(w.timebox.isEnabled())
            commit.reset_mock()

            w.implied_sequence = 0
            self.include_extra_part = True
            extra_cb.toggled.emit(True)
            self.assertEqual(w.implied_sequence, 1)
            commit.assert_called_once()
            self.assertTrue(w.datebox.isEnabled())
            self.assertTrue(w.timebox.isEnabled())
            commit.reset_mock()

            w.implied_sequence = 0
            w.unit = 0
            unit_combo.textActivated.emit(unit_combo.itemText(0))
            self.assertEqual(w.implied_sequence, 1)
            commit.assert_called_once()
            self.assertTrue(w.datebox.isEnabled())
            self.assertTrue(w.timebox.isEnabled())
            commit.reset_mock()

            w.implied_sequence = 0
            self.include_extra_part = False
            extra_cb.toggled.emit(False)
            self.assertEqual(w.implied_sequence, 1)
            commit.assert_called_once()
            self.assertFalse(w.datebox.isEnabled())
            self.assertTrue(w.timebox.isEnabled())
            commit.reset_mock()

            w.implied_sequence = 0
            step_line.editingFinished.emit()
            commit.assert_called_once()

    def test_on_time_changed_callbacks(self):
        w = self.widget
        with patch.object(w.commit, 'deferred') as commit:
            for edit in chain(w.date_edits, w.time_edits):
                w.implied_sequence = 0
                if isinstance(edit, QLineEdit):
                    edit.mousePressEvent(QMouseEvent(
                        QMouseEvent.MouseButtonPress,
                        QPointF(3, 3), QPointF(edit.mapToGlobal(QPoint(3, 3))),
                        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
                else:
                    edit.currentIndexChanged.emit(0)
                self.assertEqual(w.implied_sequence, 1, str(edit))
                commit.assert_called_once()
                commit.reset_mock()

    def test_time_reading_and_validation(self):
        w = self.widget
        w.commit.deferred = Mock()
        # Dates before 2020 have invalid date
        # 2020 is correct
        # Dates after 2020 have invalid time
        for time in ((2020, 2, 29, 23, 59, 59),
                     (1970, 1, 32, 0, 0, 0),
                     (1917, 2, 29, 0, 0, 0),
                     (2016, 2, 30, 0, 0, 0),
                     (2022, 11, 2, 24, 0, 0),
                     (2022, 11, 2, 23, 60, 0),
                     (2022, 11, 2, 23, 0, 60)):
            for val, edit in zip(time, chain(w.date_edits, w.time_edits)):
                if isinstance(edit, QLineEdit):
                    edit.setText(str(val))
                else:
                    edit.setCurrentIndex(val - 1)

            w.include_extra_part = True
            w._on_time_changed()
            self.assertEqual(w.start_date, time[:3])
            self.assertEqual(w.start_time, time[3:])
            self.assertIs(w.is_valid_time(), time[0] == 2020)
            self.assertEqual(w.get_time(), w.start_date + w.start_time)

            w.include_extra_part = False
            w.unit = w.controls.unit.itemText(0)
            # read_start_time still reads all
            w._on_time_changed()
            self.assertEqual(w.start_date, time[:3])
            self.assertEqual(w.start_time, time[3:])
            # Zero start date
            self.assertEqual(w.get_time(), (1970, 1, 1) + w.start_time)
            # Those before 2020 have invalid date
            self.assertIs(w.is_valid_time(), time[0] != 2022)

            w.include_extra_part = False
            w.unit = w.controls.unit.itemText(5)
            # read_start_time still reads all
            w._on_time_changed()
            self.assertEqual(w.start_date, time[:3])
            self.assertEqual(w.start_time, time[3:])
            # Zero start time
            self.assertEqual(w.get_time(), w.start_date + (0, 0, 0))
            # Dates after 2020 have invalid time
            self.assertIs(w.is_valid_time(), time[0] >= 2020)

    def test_empty_line_edits(self):
        w = self.widget
        for edit in chain(w.date_edits, w.time_edits):
            if isinstance(edit, QLineEdit):
                edit.setText("")
            else:
                edit.setCurrentIndex(0)
        w._on_time_changed()
        self.assertEqual(w.start_date, (2000, 1, 1))
        self.assertEqual(w.start_time, (0, 0, 0))

    def test_set_data(self):
        w = self.widget
        w.implied_sequence = 0

        with patch.object(w.commit, 'now') as commit:
            self.send_signal(w.Inputs.data, Table("iris"))
            self.assertEqual(len(w.var_combo.model()), 4)
            self.assertEqual(w.attribute, "sepal length")
            w.attribute = "petal length"
            commit.assert_called_once()
            commit.reset_mock()

            self.send_signal(w.Inputs.data, None)
            self.assertEqual(len(w.var_combo.model()), 0)
            self.assertEqual(w.attribute, "petal length")  # Kept as hint!
            commit.assert_called_once()
            commit.reset_mock()

            self.send_signal(w.Inputs.data, Table("iris"))
            self.assertEqual(len(w.var_combo.model()), 4)
            self.assertEqual(w.attribute, "petal length")
            commit.assert_called_once()
            commit.reset_mock()

            # All of above shouldn't have switched to `implied_sequence`
            self.assertEqual(w.implied_sequence, 0)

            self.send_signal(w.Inputs.data, Table("zoo"))
            self.assertEqual(w.implied_sequence, 1)
            self.assertEqual(len(w.var_combo.model()), 0)
            self.assertEqual(w.attribute, "petal length")
            self.assertEqual(w.implied_sequence, 1)
            self.assertFalse(w.controls.implied_sequence.buttons[0].isEnabled())
            commit.assert_called_once()
            commit.reset_mock()

    def test_series_from_variable(self):
        w = self.widget
        w.implied_sequence = 0
        self.send_signal(w.Inputs.data, self.data)

        w.attribute = "x"
        ts = w._series_from_variable()
        np.testing.assert_equal(
            ts.X,
            [[0., -1., 2.],
             [2., 0., np.nan],
             [0., 1., 0.],
             [np.nan, 3.1, 2.7]])
        self.assertFalse(w.Warning.nan_times.is_shown())

        w.attribute = "y"
        ts = w._series_from_variable()
        np.testing.assert_equal(
            ts.X,
            [[0., 1., 0.],
             [0., -1., 2.],
             [np.nan, 3.1, 2.7]])
        self.assertTrue(w.Warning.nan_times.is_shown())

        w.attribute = "m"
        ts = w._series_from_variable()
        np.testing.assert_equal(
            ts.X,
            [[0., 1., 0.],
             [np.nan, 3.1, 2.7],
             [2., 0., np.nan]])

    def test_series_by_sequence(self):
        def assert_stamps(stamps, offset):
            stamps = np.asarray(stamps)
            offset = timestamp(datetime(*offset, 0, timezone.utc))
            ts = w._series_by_sequence()
            np.testing.assert_equal(ts.time_values, stamps + offset)

        w = self.widget
        w.implied_sequence = 1
        self.send_signal(w.Inputs.data, self.data)

        w.start_date = (2022, 11, 3)
        w.start_time = (11, 13, 45)

        w.include_extra_part = False
        w.unit = "Seconds"
        w.steps = 1
        assert_stamps(np.arange(4), (1970, 1, 1, 11, 13, 45))

        w.unit = "Seconds"
        w.steps = 8
        assert_stamps(np.arange(4) * 8, (1970, 1, 1, 11, 13, 45))

        w.unit = "Minutes"
        w.steps = 1
        assert_stamps(np.arange(4) * 60, (1970, 1, 1, 11, 13, 45))

        w.unit = "Minutes"
        w.steps = 8
        assert_stamps(np.arange(4) * 8 * 60, (1970, 1, 1, 11, 13, 45))

        w.unit = "Hours"
        w.steps = 8
        assert_stamps(np.arange(4) * 8 * 3600, (1970, 1, 1, 11, 13, 45))

        w.unit = "Days"
        w.steps = 8
        assert_stamps(np.arange(4) * 8 * 3600 * 24, (2022, 11, 3, 0, 0, 0))

        w.unit = "Months"
        w.steps = 1
        np.testing.assert_equal(
            [timestamp(datetime(2022, 11, 3, 0, 0, 0, 0, timezone.utc)),
             timestamp(datetime(2022, 12, 3, 0, 0, 0, 0, timezone.utc)),
             timestamp(datetime(2023, 1, 3, 0, 0, 0, 0, timezone.utc)),
             timestamp(datetime(2023, 2, 3, 0, 0, 0, 0, timezone.utc))],
            w._series_by_sequence().time_values
        )

        w.unit = "Months"
        w.steps = 3
        np.testing.assert_equal(
            [timestamp(datetime(2022, 11, 3, 0, 0, 0, 0, timezone.utc)),
             timestamp(datetime(2023, 2, 3, 0, 0, 0, 0, timezone.utc)),
             timestamp(datetime(2023, 5, 3, 0, 0, 0, 0, timezone.utc)),
             timestamp(datetime(2023, 8, 3, 0, 0, 0, 0, timezone.utc))],
            w._series_by_sequence().time_values
        )

        w.unit = "Years"
        w.steps = 3
        np.testing.assert_equal(
            [timestamp(datetime(2022, 11, 3, 0, 0, 0, 0, timezone.utc)),
             timestamp(datetime(2025, 11, 3, 0, 0, 0, 0, timezone.utc)),
             timestamp(datetime(2028, 11, 3, 0, 0, 0, 0, timezone.utc)),
             timestamp(datetime(2031, 11, 3, 0, 0, 0, 0, timezone.utc))],
            w._series_by_sequence().time_values
        )

        w.include_extra_part = True
        w.unit = "Seconds"
        w.steps = 1
        assert_stamps(np.arange(4), (2022, 11, 3, 11, 13, 45))

        w.unit = "Seconds"
        w.steps = 8
        assert_stamps(np.arange(4) * 8, (2022, 11, 3, 11, 13, 45))

        w.unit = "Minutes"
        w.steps = 1
        assert_stamps(np.arange(4) * 60, (2022, 11, 3, 11, 13, 45))

        w.unit = "Minutes"
        w.steps = 8
        assert_stamps(np.arange(4) * 8 * 60, (2022, 11, 3, 11, 13, 45))

        w.unit = "Months"
        w.steps = 3
        np.testing.assert_equal(
            [timestamp(datetime(2022, 11, 3, 11, 13, 45, 0, timezone.utc)),
             timestamp(datetime(2023, 2, 3, 11, 13, 45, 0, timezone.utc)),
             timestamp(datetime(2023, 5, 3, 11, 13, 45, 0, timezone.utc)),
             timestamp(datetime(2023, 8, 3, 11, 13, 45, 0, timezone.utc))],
            w._series_by_sequence().time_values
        )

        w.unit = "Years"
        w.steps = 3
        np.testing.assert_equal(
            [timestamp(datetime(2022, 11, 3, 11, 13, 45, 0, timezone.utc)),
             timestamp(datetime(2025, 11, 3, 11, 13, 45, 0, timezone.utc)),
             timestamp(datetime(2028, 11, 3, 11, 13, 45, 0, timezone.utc)),
             timestamp(datetime(2031, 11, 3, 11, 13, 45, 0, timezone.utc))],
            w._series_by_sequence().time_values
        )

    def test_series_by_sequence_invalid_date(self):
        w = self.widget
        errtime = w.Error.invalid_time
        self.send_signal(w.Inputs.data, self.data)

        w.start_date = (2022, 11, 3)
        w.start_time = (11, 13, 45)

        # All fine
        w.include_extra_part = False
        self.assertIsNotNone(w._series_by_sequence())
        self.assertFalse(errtime.is_shown())

        # Date is invalid, but ignored -- should be fine
        w.unit = "Hours"
        w.start_date = (2022, 11, 31)
        self.assertIsNotNone(w._series_by_sequence())
        self.assertFalse(errtime.is_shown())

        # Time is invalid
        w.start_time = (11, 60, 45)
        self.assertIsNone(w._series_by_sequence())
        self.assertTrue(errtime.is_shown())
        errtime.clear()  # Errors are cleared by commit, not _series_by_sequence

        # Date is valid; time is invalid but ignored
        w.unit = "Days"
        w.start_date = (2022, 11, 3)
        w.start_time = (11, 60, 45)
        self.assertIsNotNone(w._series_by_sequence())
        self.assertFalse(errtime.is_shown())

        # Date is invalid
        w.start_date = (2022, 11, 31)
        self.assertIsNone(w._series_by_sequence())
        self.assertTrue(errtime.is_shown())
        errtime.clear()  # Errors are cleared by commit, not _series_by_sequence

        w.include_extra_part = True

        # Date is invalid, time is invalid and *not* ignored
        w.start_date = (2022, 11, 3)
        w.start_time = (11, 60, 45)
        self.assertIsNone(w._series_by_sequence())
        self.assertTrue(errtime.is_shown())
        errtime.clear()  # Errors are cleared by commit, not _series_by_sequence

        # Date is invalid, time is invalid and *not* ignored
        w.unit = "Hours"
        w.start_date = (2022, 11, 31)
        w.start_time = (11, 59, 45)
        self.assertIsNone(w._series_by_sequence())
        self.assertTrue(errtime.is_shown())

    def test_series_by_sequence_year_out_of_range(self):
        w = self.widget
        erryear = w.Error.year_out_of_range
        self.send_signal(w.Inputs.data, self.data)

        w.unit = "Years"

        w.steps = 10000
        w.start_date = (2022, 11, 3)
        w.start_time = (11, 13, 45)
        self.assertIsNone(w._series_by_sequence())
        self.assertTrue(erryear.is_shown())
        erryear.clear()  # cleared by commit

        w.steps = 1
        self.assertIsNotNone(w._series_by_sequence())
        self.assertFalse(erryear.is_shown())

        w.start_date = (10101, 1, 31)
        self.assertIsNone(w._series_by_sequence())
        self.assertTrue(erryear.is_shown())
        erryear.clear()  # cleared by commit

        w.start_date = (-10101, 1, 31)
        self.assertIsNone(w._series_by_sequence())
        self.assertTrue(erryear.is_shown())

    def test_series_by_sequence_time_format(self):
        w = self.widget
        self.send_signal(w.Inputs.data, self.data)

        w.unit = "Hours"

        w.include_extra_part = False
        ts = w._series_by_sequence()
        self.assertEqual(ts.time_variable.have_date, 0)
        self.assertEqual(ts.time_variable.have_time, 1)

        w.include_extra_part = True
        ts = w._series_by_sequence()
        self.assertEqual(ts.time_variable.have_date, 1)
        self.assertEqual(ts.time_variable.have_time, 1)

        w.unit = "Days"

        w.include_extra_part = False
        ts = w._series_by_sequence()
        self.assertEqual(ts.time_variable.have_date, 1)
        self.assertEqual(ts.time_variable.have_time, 0)

        w.include_extra_part = True
        ts = w._series_by_sequence()
        self.assertEqual(ts.time_variable.have_date, 1)
        self.assertEqual(ts.time_variable.have_time, 1)

    def test_series_by_sequence_reraises_exceptions(self):
        w = self.widget
        self.send_signal(w.Inputs.data, self.data)
        with patch("orangecontrib.timeseries.Timeseries."
                   "make_timeseries_from_sequence", side_effect=ValueError):
            self.assertRaises(ValueError, w._series_by_sequence)

    def test_set_data_attr_from_setting(self):
        w = self.create_widget(
            OWTableToTimeseries,
            stored_settings=dict(implied_sequence=1, attribute="sepal width"))
        self.send_signal(w.Inputs.data, Table("iris"))
        self.assertEqual(w.attribute, "sepal width")
        self.assertEqual(w.var_combo.currentText(), "sepal width")

    def test_report(self):
        w = self.widget
        self.send_signal(w.Inputs.data, self.data)

        w.implied_sequence = 0
        w.send_report()

        w.implied_sequence = 1
        w.send_report()

    def test_migrate_settings_1_to_2(self):
        set_orig = {'autocommit': True,
                    'controlAreaVisible': True,
                    'radio_sequential': 2,
                    'savedWidgetGeometry': b'\x01\xd9\xd0\xcb\x00\x03\x00\x00\x00\x00\x02I\x00\x00\x012\x00\x00\x03\x8b\x00\x00\x02\x96\x00\x00\x02I\x00\x00\x01N\x00\x00\x03\x8b\x00\x00\x02\x96\x00\x00\x00\x00\x02\x00\x00\x00\x05\xe8\x00\x00\x02I\x00\x00\x01N\x00\x00\x03\x8b\x00\x00\x02\x96',
                    'selected_attr': '',
                    '__version__': 1}

        settings = deepcopy(set_orig)
        settings['context_settings'] = [
            Context(
                attributes={'sepal length': 2, 'sepal width': 2,
                            'petal length': 2, 'petal width': 2, 'iris': 1},
                values={'implied_sequence': (0, -2),
                        'order': ('petal length', 102),
                        '__version__': 1})]
        OWTableToTimeseries.migrate_settings(settings, 1)
        self.assertEqual(settings["implied_sequence"], 0)
        self.assertEqual(settings["attribute"], "petal length")
        self.assertFalse("context_settings" in settings)

        settings = deepcopy(set_orig)
        settings['context_settings'] = [
            Context(
                attributes={'sepal length': 2, 'sepal width': 2,
                            'petal length': 2, 'petal width': 2, 'iris': 1},
                values={'implied_sequence': (1, -2),
                        'order': ('petal length', 102),
                        '__version__': 1})]
        OWTableToTimeseries.migrate_settings(settings, 1)
        self.assertEqual(settings["implied_sequence"], 1)
        self.assertEqual(settings["attribute"], "petal length")
        self.assertFalse("context_settings" in settings)

        settings = deepcopy(set_orig)
        settings['context_settings']: []
        OWTableToTimeseries.migrate_settings(settings, 1)
        self.assertFalse("context_settings" in settings)

        settings = deepcopy(set_orig)
        OWTableToTimeseries.migrate_settings(settings, 1)
        self.assertFalse("context_settings" in settings)


if __name__ == "__main__":
    unittest.main()
