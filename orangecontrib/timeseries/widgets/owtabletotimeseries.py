from itertools import chain

import numpy as np

from AnyQt.QtWidgets import QGridLayout

from orangewidget.utils.widgetpreview import WidgetPreview
from Orange.data import Table
from Orange.widgets import widget, gui, settings
from Orange.widgets.settings import DomainContextHandler
from Orange.widgets.utils.itemmodels import VariableListModel
from Orange.widgets.widget import Input, Output

from orangecontrib.timeseries import Timeseries


class OWTableToTimeseries(widget.OWWidget):
    name = 'As Timeseries'
    description = 'Reinterpret data table as a time series.'
    icon = 'icons/TableToTimeseries.svg'
    priority = 10

    class Inputs:
        data = Input("Data", Table)

    class Outputs:
        time_series = Output("Time series", Timeseries)

    want_main_area = False
    resizing_enabled = False

    # Old settings that can't be migrated, but can be supported
    selected_attr = settings.Setting('')
    radio_sequential = settings.Setting(2)

    settingsHandler = DomainContextHandler()
    implied_sequence = settings.ContextSetting(0)
    order = settings.ContextSetting(None)
    autocommit = settings.Setting(True)

    class Information(widget.OWWidget.Information):
        nan_times = widget.Msg('Some values of chosen sequential attribute '
                               '"{}" are NaN, and have been omitted')

    def __init__(self):
        self.data = None

        layout = QGridLayout()
        gui.widgetBox(self.controlArea, True, orientation=layout)
        group = gui.radioButtons(
            None, self, 'implied_sequence', callback=self.commit.deferred)
        layout.addWidget(
            gui.appendRadioButton(
                group, 'Sequential attribute:', addToLayout=False),
            0, 0)
        layout.addWidget(
            gui.comboBox(
                None, self, 'order', model=VariableListModel(),
                callback=self._on_attribute_changed),
            0, 1)
        layout.addWidget(
            gui.appendRadioButton(
                group, 'Sequence implied by instance order', addToLayout=False),
            1, 0, 1, 2)

        gui.auto_commit(self.controlArea, self, 'autocommit', '&Apply')
        # TODO: seasonally adjust data (select attributes & season cycle length (e.g. 12 if you have monthly data))

    def _on_attribute_changed(self):
        self.implied_sequence = 0
        self.commit.deferred()

    @Inputs.data
    def set_data(self, data):
        self.closeContext()
        self.data = data
        model = self.controls.order.model()
        if data:
            valid = (var
                     for var in chain(data.domain.variables, data.domain.metas)
                     if var.is_continuous)
            model[:] = sorted(valid, key=lambda var: not var.is_time)
        else:
            model.clear()

        if not model:
            self.implied_sequence = 1
        # radio_sequential and selected_attr can't be migrated, but can be used
        elif self.radio_sequential != 2:
            self.implied_sequence = self.radio_sequential
        if model:
            if self.selected_attr in data.domain \
                    and data.domain[self.selected_attr] in model:
                self.order = data.domain[self.selected_attr]
            else:
                self.order = getattr(data, "time_variable", model[0])
        self.controls.implied_sequence.buttons[0].setDisabled(not model)
        self.openContext(data)
        self.commit.now()

    @gui.deferred
    def commit(self):
        data = self.data
        self.Information.clear()
        if not data:
            self.Outputs.time_series.send(None)
            return

        if self.order is None:
            ts = Timeseries.make_timeseries_from_sequence(data)
        else:
            ts = Timeseries.make_timeseries_from_continuous_var(data, self.order)
            # Warn if instances are omitted because of nans in selected attr
            times, sparse = data.get_column_view(self.order)
            if sparse:
                times = times.data
            if np.isnan(times).any():
                self.Information.nan_times(self.order.name)

        self.Outputs.time_series.send(ts)


if __name__ == "__main__":
    data = Timeseries.from_file('airpassengers')
    WidgetPreview(OWTableToTimeseries).run(data)
