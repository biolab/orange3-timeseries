from itertools import chain

import numpy as np

from Orange.data import Table, ContinuousVariable, TimeVariable, Domain
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.itemmodels import VariableListModel
from Orange.widgets.widget import Input, Output

from orangecontrib.timeseries import Timeseries


class OWTableToTimeseries(widget.OWWidget):
    name = 'As Timeseries'
    description = ('Reinterpret data table as a time series object.')
    icon = 'icons/TableToTimeseries.svg'
    priority = 10

    class Inputs:
        data = Input("Data", Table)

    class Outputs:
        time_series = Output("Time series", Timeseries)

    want_main_area = False
    resizing_enabled = False

    radio_sequential = settings.Setting(0)
    selected_attr = settings.Setting('')
    autocommit = settings.Setting(True)

    class Error(widget.OWWidget.Error):
        nan_times = widget.Msg('Some values of chosen sequential attribute '
                               '"{}" are NaN, which makes the values '
                               'impossible to sort')

    def __init__(self):
        self.data = None
        box = gui.vBox(self.controlArea, 'Sequence')
        group = gui.radioButtons(box, self, 'radio_sequential',
                                 callback=self.on_changed)
        hbox = gui.hBox(box)
        gui.appendRadioButton(group, 'Sequential attribute:',
                              insertInto=hbox)

        attrs_model = self.attrs_model = VariableListModel()
        combo_attrs = self.combo_attrs = gui.comboBox(
            hbox, self, 'selected_attr',
            callback=self.on_changed,
            sendSelectedValue=True)
        combo_attrs.setModel(attrs_model)

        gui.appendRadioButton(group, 'Sequence is implied by instance order',
                              insertInto=box)

        gui.auto_commit(self.controlArea, self, 'autocommit', '&Apply')
        # TODO: seasonally adjust data (select attributes & season cycle length (e.g. 12 if you have monthly data))

    @Inputs.data
    def set_data(self, data):
        self.data = data
        self.attrs_model.clear()
        if self.data is None:
            self.commit()
            return
        if data.domain.has_continuous_attributes():
            vars = [var for var in data.domain.variables if var.is_time] + \
                   [var for var in data.domain.metas if var.is_time] + \
                   [var for var in data.domain.variables
                    if var.is_continuous and not var.is_time] + \
                   [var for var in data.domain.metas if var.is_continuous and
                    not var.is_time]
            self.attrs_model.wrap(vars)
            self.selected_attr = data.time_variable.name if getattr(data, 'time_variable', False) else vars[0].name
        self.on_changed()

    def on_changed(self):
        self.commit()

    def commit(self):
        data = self.data
        self.Error.clear()
        if data is None or (self.selected_attr not in data.domain and not self.radio_sequential):
            self.Outputs.time_series.send(None)
            return

        attrs = data.domain.attributes
        cvars = data.domain.class_vars
        metas = data.domain.metas
        X = data.X
        Y = np.column_stack((data.Y,))  # make 2d
        M = data.metas

        # Set sequence attribute
        if self.radio_sequential:
            for i in chain(('',), range(10)):
                name = '__seq__' + str(i)
                if name not in data.domain:
                    break
            time_var = ContinuousVariable(name)
            attrs = attrs.__class__((time_var,)) + attrs
            X = np.column_stack((np.arange(1, len(data) + 1), X))
            data = Table(Domain(attrs, cvars, metas), X, Y, M)
        else:
            # Or make a sequence attribute one of the existing attributes
            # and sort all values according to it
            time_var = data.domain[self.selected_attr]
            values = Table.from_table(Domain([], [], [time_var]),
                                      source=data).metas.ravel()
            if np.isnan(values).any():
                self.Error.nan_times(time_var.name)
                self.Outputs.time_series.send(None)
                return
            ordered = np.argsort(values)
            if (ordered != np.arange(len(ordered))).any():
                data = data[ordered]

        ts = Timeseries(data.domain, data)
        # TODO: ensure equidistant
        ts.time_variable = time_var
        self.Outputs.time_series.send(ts)


if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication

    a = QApplication([])
    ow = OWTableToTimeseries()

    data = Timeseries('airpassengers')
    ow.set_data(data)

    ow.show()
    a.exec()
