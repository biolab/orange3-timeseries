import dataclasses
import string
from itertools import chain
from typing import Dict, Optional, Tuple
import calendar
import datetime

from dateutil.relativedelta import relativedelta

from AnyQt.QtCore import Qt
from AnyQt.QtWidgets import \
    QGridLayout, QStyle, QComboBox, QLabel, QLineEdit, QSizePolicy
from AnyQt.QtGui import QFontMetrics, QIntValidator

from orangewidget.utils.widgetpreview import WidgetPreview

from Orange.data import Table, TimeVariable
from Orange.widgets import widget, gui
from Orange.widgets.settings import Setting
from Orange.widgets.utils.itemmodels import VariableListModel, signal_blocking
from Orange.widgets.widget import Input, Output

from orangecontrib.timeseries import Timeseries, functions


@dataclasses.dataclass
class StepOptionsDef:
    label: str
    delta: Optional[relativedelta] = None
    sub_daily: bool = False

    def __post_init__(self):
        if self.delta is None:
            self.delta = relativedelta(**{self.label.lower(): 1})
        self.sub_daily = not (self.delta.days or self.delta.weeks
                              or self.delta.months or self.delta.years)


StepOptions: Dict[str, relativedelta] = {
    label: StepOptionsDef(label)
    for label in ["Seconds", "Minutes", "Hours",
                  "Days", "Weeks", "Months", "Years"]
}
StepOptions["Centuries"] = \
    StepOptionsDef("Centuries", relativedelta(years=100))


class OWTableToTimeseries(widget.OWWidget):
    name = 'Form Timeseries'
    description = 'Reinterpret data table as a time series.'
    icon = 'icons/TableToTimeseries.svg'
    priority = 10

    class Inputs:
        data = Input("Data", Table)

    class Outputs:
        time_series = Output("Time series", Timeseries)

    class Error(widget.OWWidget.Error):
        invalid_time = widget.Msg("Invalid time")
        year_out_of_range = widget.Msg("{}.")

    class Warning(widget.OWWidget.Warning):
        nan_times = widget.Msg("Rows with missing values of '{}' are skipped")

    want_main_area = False
    resizing_enabled = False

    implied_sequence = Setting(0)
    steps = Setting(1)
    unit = Setting(next(iter(StepOptions)))
    include_extra_part = Setting(True)
    start_date = Setting((2022, 11, 1))
    start_time = Setting((0, 0, 0))
    attribute = Setting(None)
    autocommit = Setting(True)

    extra_part_labels = ["Include time of day in time stamp",
                         "Include date in time stamp"]

    def __init__(self):
        self.data = None

        outbox = gui.vBox(self.controlArea, box=True)

        style = self.style()
        indent = style.pixelMetric(QStyle.PM_RadioButtonLabelSpacing) \
            + style.pixelMetric(QStyle.PM_ExclusiveIndicatorWidth)
        fmetr = QFontMetrics(self.font())
        numwidth = max(fmetr.boundingRect(c).width() for c in string.digits)

        group = gui.radioButtons(
            None, self, 'implied_sequence', callback=self.commit.deferred)
        gui.appendRadioButton(
            group, "Select the column with date", insertInto=outbox)
        hbox = gui.indentedBox(outbox, indent, orientation=Qt.Horizontal)
        hbox.layout().addWidget(QLabel("Variable: "))
        self.var_combo = combo = QComboBox()
        combo.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        combo.setModel(VariableListModel())
        combo.activated.connect(self._on_attribute_changed)
        hbox.layout().addWidget(combo)
        gui.separator(outbox, 16)

        gui.appendRadioButton(
            group, 'Sequence implied by instance order', insertInto=outbox)

        calbox = gui.indentedBox(outbox, indent)
        grid = QGridLayout()
        gui.widgetBox(calbox, orientation=grid)

        rows = 0
        rows += self._add_step_controls(grid, rows, numwidth)
        rows += self._add_format_controls(grid, rows)
        rows += self._add_start_controls(grid, rows, numwidth)
        gui.auto_commit(self.controlArea, self, 'autocommit', '&Apply')

    def _add_start_controls(self, layout, row, numwidth):
        layout.addWidget(QLabel("Start: "), row, 0)
        self.datebox = gui.hBox(None)
        y, m, d = self.start_date
        numargs = dict(alignment=Qt.AlignCenter, maximumWidth=numwidth * 4)
        self.date_edits = (
            QLineEdit(str(y),
                      alignment=Qt.AlignRight, maximumWidth=numwidth * 6),
            combo := QComboBox(),
            QLineEdit(str(d), **numargs)
        )
        combo.addItems(calendar.month_name[1:])
        combo.setCurrentIndex(m)
        combo.setMinimumContentsLength(max(map(len, calendar.month_name[1:])))
        for edit in self.date_edits:
            self.datebox.layout().addWidget(edit)
        gui.rubber(self.datebox)
        layout.addWidget(self.datebox, row, 1, 1, -1)

        self.timebox = gui.hBox(None)
        self.time_edits = tuple(
            QLineEdit(f"{val:02}", **numargs)
            for val in self.start_time)
        for i, edit in enumerate(self.time_edits):
            self.timebox.layout().addWidget(QLabel(["⏱", ":", ":"][i]))
            self.timebox.layout().addWidget(edit)
        gui.rubber(self.timebox)
        layout.addWidget(self.timebox, row + 1, 1, 1, -1)

        validator = QIntValidator()
        for edit in chain(self.date_edits, self.time_edits):
            if isinstance(edit, QLineEdit):
                edit.setValidator(validator)
                edit.editingFinished.connect(self._on_time_changed)
            else:
                edit.currentIndexChanged.connect(self._on_time_changed)

        self._update_start_controls()
        self.Error.invalid_time(shown=not self.is_valid_time())
        return 2

    def _update_start_controls(self):
        self.controls.include_extra_part.setText(
            self.extra_part_labels[StepOptions[self.unit].sub_daily])
        self.timebox.setEnabled(self.use_time)
        self.datebox.setEnabled(self.use_date)

    def _add_step_controls(self, layout, row, numwidth):
        layout.addWidget(QLabel("Step: "), row, 0)
        box = gui.hBox(None)
        le = gui.lineEdit(
            box, self, "steps",
            alignment=Qt.AlignRight, maximumWidth=4 * numwidth,
            valueType=int, validator=QIntValidator(),
        )
        le.editingFinished.connect(self._on_time_settings_changed)
        gui.comboBox(
            box, self, "unit", items=list(StepOptions),
            callback=self._on_time_settings_changed, sendSelectedValue=True
        )
        layout.addWidget(box, row, 1, 1, -1)
        return 1

    def _add_format_controls(self, layout, row):
        layout.addWidget(
            gui.checkBox(
                None, self, "include_extra_part", self.extra_part_labels[0],
                callback=self._on_time_settings_changed), row, 1, 1, -1)
        return 1

    @property
    def use_time(self):
        return self.include_extra_part or StepOptions[self.unit].sub_daily

    @property
    def use_date(self):
        return self.include_extra_part or not StepOptions[self.unit].sub_daily

    def _on_attribute_changed(self):
        self.implied_sequence = 0
        self.commit.deferred()

    def _on_time_settings_changed(self):
        self.implied_sequence = 1
        self._update_start_controls()
        self.commit.deferred()

    def _on_time_changed(self):
        self.implied_sequence = 1
        self.read_start_time()
        self.commit.deferred()

    def read_start_time(self) -> Optional[Tuple[int, int, int, int, int, int]]:
        ye, me, de = self.date_edits
        self.start_date = (int(ye.text()), me.currentIndex() + 1, int(de.text()))
        self.start_time = tuple(int(edit.text()) for edit in self.time_edits)

    def get_time(self):
        return (self.start_date if self.use_date else (1970, 1, 1)) \
            + (self.start_time if self.use_time else (0, 0, 0))

    def is_valid_time(self):
        y, m, d, ho, mi, se = self.get_time()
        _, days_in_month = calendar.monthrange(y, m)
        return 1 <= d <= days_in_month \
               and 0 <= ho < 24 and 0 <= mi < 60 and 0 <= se < 60

    @Inputs.data
    def set_data(self, data):
        if not data:
            self.data = None
            self.var_combo.model().clear()
            self.commit.now()
            return

        with signal_blocking(self.var_combo):
            model = self.var_combo.model()
            self.data = data
            time_vars = [
                var for var in chain(data.domain.variables, data.domain.metas)
                if var.is_time]
            cont_vars = [
                var for var in chain(data.domain.variables, data.domain.metas)
                if var.is_continuous and not var.is_time]
            separator = [VariableListModel.Separator
                         ] if len(time_vars) > 1 and cont_vars else []
            model[:] = time_vars + separator + cont_vars

            self.controls.implied_sequence.buttons[0].setDisabled(not model)
            if not model:
                self.implied_sequence = 1
            if model and self.attribute not in [var.name
                                                for var in time_vars + cont_vars]:
                self.attribute = getattr(data, "time_variable", model[0]).name
        self.commit.now()

    @gui.deferred
    def commit(self):
        self.Warning.clear()
        self.Error.year_out_of_range.clear()
        self.Error.invalid_time.clear()
        if not self.data:
            ts = None
        elif self.implied_sequence == 0:
            ts = self._series_from_variable()
        else:
            ts = self._series_by_sequence()
        self.Outputs.time_series.send(ts)

    def _series_from_variable(self):
        data = self.data
        time_var = data.domain[self.attribute]
        ts = Timeseries.make_timeseries_from_continuous_var(data, time_var)
        self.Warning.nan_times(self.attribute,
                               shown=ts is None or len(data) != len(ts))
        return ts

    def _series_by_sequence(self):
        if not self.is_valid_time():
            self.Error.invalid_time()
            return None

        start = datetime.datetime(*self.get_time(), 0, datetime.timezone.utc)
        delta = int(self.steps) * StepOptions[self.unit].delta
        try:
            ts = Timeseries.make_timeseries_from_sequence(
                self.data, delta, start,
                have_date=self.use_date, have_time=self.use_time)
        except ValueError as exc:
            msg = str(exc)
            if msg.startswith("year") and msg.endswith("out of range"):
                self.Error.year_out_of_range(msg.capitalize())
                return None
            else:
                raise
        return ts

    def send_report(self):
        if self.implied_sequence == 0:
            self.report_items((("Assigned time variable", self.attribute), ))
        else:
            timevar = TimeVariable(
                "foo", have_date=self.use_date, have_time=self.use_time)
            start_time = timevar.str_val(
                functions.timestamp(datetime.datetime(*self.get_time(),
                                    0, datetime.timezone.utc)))
            self.report_items((
                ("Start time", start_time),
                ("Step", f"{self.steps} {self.unit.lower()}")
            ))


if __name__ == "__main__":
    data = Timeseries.from_file('airpassengers')
    WidgetPreview(OWTableToTimeseries).run(data)
