import numpy as np

from AnyQt.QtWidgets import QListView

from Orange.data import Table, Domain, ContinuousVariable
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.itemmodels import VariableListModel

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.utils import available_name


class Output:
    TIMESERIES = 'Time series'


class OWDifference(widget.OWWidget):
    name = 'Difference'
    description = 'Make the time series stationary by replacing it with ' \
                  '1st or 2nd order discrete difference along its values. '
    icon = 'icons/Difference.svg'
    priority = 570

    inputs = [("Time series", Table, 'set_data')]
    outputs = [("Time series", Timeseries)]

    want_main_area = False
    resizing_enabled = False

    diff_order = settings.Setting(1)
    shift_period = settings.Setting(1)
    invert_direction = settings.Setting(True)
    selected = settings.Setting([])
    autocommit = settings.Setting(False)

    UserAdviceMessages = [
        widget.Message('You can difference the series up to the 2nd order. '
                       'However, if you shift the series by other than 1 step, '
                       'a differencing order of 1 is always assumed.',
                       'diff-shift')
    ]

    def __init__(self):
        self.data = None
        box = gui.vBox(self.controlArea, 'Differencing')
        self.order_spin = gui.spin(
            box, self, 'diff_order', 1, 2,
            label='Differencing order:',
            callback=self.on_changed,
            tooltip='The value corresponds to n-th order numerical '
                    'derivative of the series. \nThe order is fixed to 1 '
                    'if the shift period is other than 1.')
        gui.spin(box, self, 'shift_period', 1, 100,
                 label='Shift:',
                 callback=self.on_changed,
                 tooltip='Set this to other than 1 if you don\'t want to '
                         'compute differences for subsequent values but for '
                         'values shifted number of spaces apart. \n'
                         'If this value is different from 1, differencing '
                         'order is fixed to 1.')
        gui.checkBox(box, self, 'invert_direction',
                     label='Invert differencing direction',
                     callback=self.on_changed,
                     tooltip='Influences where the series is padded with nan '
                             'values — at the beginning or at the end.')
        self.view = view = QListView(self,
                                     selectionMode=QListView.ExtendedSelection)
        self.model = model = VariableListModel(parent=self)
        view.setModel(model)
        view.selectionModel().selectionChanged.connect(self.on_changed)
        box.layout().addWidget(view)
        gui.auto_commit(box, self, 'autocommit', '&Apply')

    def set_data(self, data):
        self.data = data = None if data is None else Timeseries.from_data_table(data)
        if data is not None:
            self.model.wrap([var for var in data.domain
                             if var.is_continuous and var is not data.time_variable])
        self.on_changed()

    def on_changed(self):
        self.order_spin.setDisabled(self.shift_period != 1)
        self.selected = [self.model[i.row()].name
                         for i in self.view.selectionModel().selectedIndexes()]
        self.commit()

    def commit(self):
        data = self.data
        if not data or not len(self.selected):
            self.send(Output.TIMESERIES, None)
            return

        X = []
        attrs = []
        invert = self.invert_direction
        shift = self.shift_period
        order = self.diff_order
        for var in self.selected:
            col = np.ravel(data[:, var])

            if invert:
                col = col[::-1]

            out = np.empty(len(col))
            if shift == 1:
                out[:-order] = np.diff(col, order)
                out[-order:] = np.nan
            else:
                out[:-shift] = col[shift:] - col[:-shift]
                out[-shift:] = np.nan

            if invert:
                out = out[::-1]

            X.append(out)

            template = '{} (diff; {})'.format(var,
                                              'order={}'.format(order) if shift == 1 else
                                              'shift={}'.format(shift))
            name = available_name(data.domain, template)
            attrs.append(ContinuousVariable(name))

        ts = Timeseries(Domain(data.domain.attributes + tuple(attrs),
                               data.domain.class_vars,
                               data.domain.metas),
                        np.column_stack((data.X, np.column_stack(X))),
                        data.Y, data.metas)
        ts.time_variable = data.time_variable
        self.send(Output.TIMESERIES, ts)


if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication

    a = QApplication([])
    ow = OWDifference()

    data = Timeseries('yahoo_MSFT')
    # Make Adjusted Close a class variable
    attrs = [var.name for var in data.domain.attributes]
    if 'Adj Close' in attrs:
        attrs.remove('Adj Close')
        data = Timeseries(Domain(attrs, [data.domain['Adj Close']], None, source=data.domain), data)

    ow.set_data(data)

    ow.show()
    a.exec()
