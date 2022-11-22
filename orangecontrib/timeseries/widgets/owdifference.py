from functools import partial
from typing import List, NamedTuple

import numpy as np

from AnyQt.QtCore import Qt
from AnyQt.QtWidgets import QListView

from Orange.data import Table, Domain, ContinuousVariable
from Orange.data.util import get_unique_names
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.itemmodels import VariableListModel, signal_blocking, \
    select_rows
from Orange.widgets.widget import Input, Output

from orangecontrib.timeseries import Timeseries
from orangewidget.utils.widgetpreview import WidgetPreview


class OpDesc(NamedTuple):
    name: str
    prefix: str


class OWDifference(widget.OWWidget):
    name = 'Difference'
    description = 'Make the time series stationary by replacing it with ' \
                  '1st or 2nd order discrete difference along its values. '
    icon = 'icons/Difference.svg'
    priority = 570
    keywords = ['difference', 'derivative', 'quotient', 'percent change']

    class Inputs:
        time_series = Input("Time series", Table)

    class Outputs:
        time_series = Output("Time series", Timeseries)

    Operations = [
        OpDesc("First order difference", "Δ"),
        OpDesc("Second order difference", "ΔΔ"),
        OpDesc("Change quotient", "q"),
        OpDesc("Percentage change", "%"),
    ]

    Diff, Diff2, Quot, Perc = range(4)

    want_main_area = False
    resizing_enabled = False

    operation = settings.Setting(Diff)
    shift_period = settings.Setting(1)
    invert_direction = settings.Setting(False)
    assume_zero_before = settings.Setting(False)
    selection: List[str] = settings.Setting([])
    autocommit = settings.Setting(True)

    def __init__(self):
        self.data = None
        self.selection = self.persistent_selection = []

        self.view = view = QListView(self,
                                     selectionMode=QListView.ExtendedSelection)
        self.model = VariableListModel(parent=self)
        view.setModel(self.model)
        view.selectionModel().selectionChanged.connect(self._selection_changed)
        self.controlArea.layout().addWidget(view)

        box = gui.vBox(self.controlArea, "Operation")
        gui.radioButtonsInBox(
            box, self, 'operation',
            [op.name for op in self.Operations],
            callback=self._operation_or_direction_changed)
        gui.separator(box)

        sp = gui.spin(
            box, self, 'shift_period', 1, 100, label='Shift:',
            controlWidth=60, alignment=Qt.AlignRight,
            callback=self.commit.deferred,
            tooltip="Sets the distance between points; 1 for consecutive points"
        )
        gui.rubber(sp.box)

        gui.checkBox(
            box, self, 'invert_direction', 'Invert differencing direction',
            callback=self._operation_or_direction_changed)

        gui.checkBox(
            box, self, 'assume_zero_before',
            'Assume zeros before start', stateWhenDisabled=False,
            callback=self.commit.deferred)

        self._update_gui_state()
        gui.auto_commit(self.buttonsArea, self, 'autocommit', '&Apply')

    def _operation_or_direction_changed(self):
        self._update_gui_state()
        self.commit.deferred()

    def _update_gui_state(self):
        self.controls.shift_period.box.setEnabled(self.operation != self.Diff2)
        self.controls.assume_zero_before.setEnabled(
            not self.invert_direction
            and self.operation in (self.Diff, self.Diff2))

    def _selection_changed(self):
        self.selection = [
            self.model.data(index)
            for index in self.view.selectionModel().selectedRows()]
        self.commit.deferred()

    @Inputs.time_series
    def set_data(self, data):
        if self.selection:
            self.persistent_selection = self.selection[:]

        if not data:
            self.data = None
            self.model.clear()
            self.commit.now()
            return

        self.data = Timeseries.from_data_table(data)
        self.model[:] = [var for var in data.domain.variables
                         if var.is_continuous and var is not
                         self.data.time_variable]

        names = [attr.name for attr in self.model]
        self.selection = [name for name in self.persistent_selection
                          if name in names]
        with signal_blocking(self.view.selectionModel()):
            select_rows(self.view,
                        [names.index(name) for name in self.selection])
        self.commit.now()

    @gui.deferred
    def commit(self):
        data = self.data
        if not data:
            self.Outputs.time_series.send(None)
            return

        attrs, columns = self.compute(data, self.selection)
        domain = data.domain
        out_domain = Domain(
            domain.attributes + attrs, domain.class_vars, domain.metas)
        ts = Timeseries.from_numpy(
            out_domain,
            np.column_stack((data.X, columns)), data.Y, data.metas,
            time_attr=data.time_variable)
        self.Outputs.time_series.send(ts)

    def compute(self, data, attr_names):
        columns = []
        attrs = []
        shift = self.shift_period
        name_prefix = self.Operations[self.operation].prefix
        name_postfix = f":{shift}" if shift != 1 else ""
        op = self.operation
        get_unique = partial(get_unique_names, data.domain)

        for name in attr_names:
            col = data.get_column(name)
            if self.invert_direction:
                col = col[::-1]

            out = np.full(len(col), np.nan)
            number_of_decimals = data.domain[name].number_of_decimals
            if op == self.Diff:
                out[shift:] = col[shift:] - col[:-shift]
                if not self.invert_direction and self.assume_zero_before:
                    out[:shift] = col[:shift]
            elif op == self.Diff2:
                out[2:] = np.diff(col, 2)
                if not self.invert_direction and self.assume_zero_before:
                    out[1] = col[1] - 2 * col[0]
                    out[0] = col[0]
            else:
                assert op in (self.Quot, self.Perc)
                quots = col[:-shift].copy()
                zeros = quots == 0
                quots[zeros] = 1
                out[shift:] = col[shift:] / quots
                if op == self.Perc:
                    out = (out - 1) * 100
                out[shift:][zeros] = np.nan
                number_of_decimals = 3
            if self.invert_direction:
                out = out[::-1]

            columns.append(out)
            attr = ContinuousVariable(
                name=get_unique(name_prefix + name + name_postfix),
                number_of_decimals=number_of_decimals)
            attrs.append(attr)

        if columns:
            columns = np.column_stack(columns)
        else:
            columns = np.zeros((len(data), 0), dtype=float)
        return tuple(attrs), columns


if __name__ == "__main__":
    WidgetPreview(OWDifference).run(set_data=Table.from_file('iris'))
