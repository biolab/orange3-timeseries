from itertools import chain, groupby
from collections import OrderedDict

import numpy as np

from AnyQt.QtWidgets import QStyledItemDelegate, QComboBox
from AnyQt.QtCore import Qt

from Orange.data import Table, Domain, TimeVariable
from Orange.widgets import widget, gui, settings
from Orange.widgets.settings import ContextSetting, DomainContextHandler
from Orange.widgets.utils.itemmodels import PyTableModel
from Orange.widgets.widget import Input, Output

from orangecontrib.timeseries import Timeseries, fromtimestamp, timestamp
from orangecontrib.timeseries.widgets.utils import ListModel
from orangecontrib.timeseries.agg_funcs import AGG_FUNCTIONS, Mode, Concatenate


class OWAggregate(widget.OWWidget):
    name = 'Aggregate'
    description = "Aggregate data in bins by second, minute, hour, day, " \
                  "week, month, or year."
    icon = 'icons/Aggregate.svg'
    priority = 560

    class Inputs:
        time_series = Input("Time series", Table)

    class Outputs:
        time_series = Output("Time series", Timeseries)

    settingsHandler = DomainContextHandler()
    variables = ContextSetting([])
    agg_funcs = ContextSetting([])

    want_main_area = False

    agg_interval = settings.Setting('day')
    autocommit = settings.Setting(False)

    AGG_TIME = OrderedDict((
        ('second', lambda date: date.replace(microsecond=0)),
        ('minute', lambda date: date.replace(second=0, microsecond=0)),
        ('hour', lambda date: date.replace(minute=0, second=0, microsecond=0)),
        ('day', lambda date: date.replace(hour=0, minute=0, second=0, microsecond=0)),
        ('week', lambda date: date.strptime(date.strftime('%Y-W%W-0'), '%Y-W%W-%w')),  # Doesn't work for years before 1000
        ('month', lambda date: date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)),
        ('year', lambda date: date.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)),
    ))

    class Error(widget.OWWidget.Error):
        no_time_variable = widget.Msg(
            'Aggregation currently requires a time series with a time variable.')

    def __init__(self):
        self.data = None

        gui.comboBox(self.controlArea, self, 'agg_interval',
                     label='Aggregate by:',
                     items=tuple(self.AGG_TIME.keys()),
                     sendSelectedValue=True,
                     orientation=Qt.Horizontal,
                     callback=lambda: self.commit)
        self.model = model = PyTableModel(parent=self, editable=[False, True])
        model.setHorizontalHeaderLabels(['Attribute', 'Aggregation function'])

        class TableView(gui.TableView):
            def __init__(self, parent):
                super().__init__(parent,
                                 editTriggers=(self.SelectedClicked |
                                               self.CurrentChanged |
                                               self.DoubleClicked |
                                               self.EditKeyPressed),
                                 )
                self.horizontalHeader().setStretchLastSection(False)
                self.setItemDelegateForColumn(1, self.ComboDelegate(self))

            class _ItemDelegate(QStyledItemDelegate):
                def updateEditorGeometry(self, widget, option, _index):
                    widget.setGeometry(option.rect)

            class ComboDelegate(_ItemDelegate):
                def __init__(self, parent):
                    super().__init__(parent)
                    self._parent = parent
                    self._combo_continuous_model = ListModel(AGG_FUNCTIONS, parent=self)
                    self._combo_discrete_model = ListModel([Mode], parent=self)
                    self._combo_string_model = ListModel([Concatenate], parent=self)

                def createEditor(self, parent, _QStyleOptionViewItem, index):
                    combo = QComboBox(parent)
                    attr = index.model()[index.row()][0]
                    combo.setModel(self._combo_continuous_model if attr.is_continuous else
                                   self._combo_discrete_model if attr.is_discrete else
                                   self._combo_string_model)
                    return combo

                def setEditorData(self, combo, index):
                    var = index.model().data(index, Qt.EditRole)
                    combo.setCurrentIndex(combo.model().indexOf(var))

                def setModelData(self, combo, model, index):
                    func = combo.model()[combo.currentIndex()]
                    model.setData(index, func, Qt.EditRole)

        view = TableView(self)
        view.setModel(model)
        self.settingsAboutToBePacked.connect(self.pack_settings)
        self.controlArea.layout().addWidget(view)
        gui.auto_commit(self.controlArea, self, 'autocommit', '&Apply')

    @Inputs.time_series
    def set_data(self, data):
        self.pack_settings()
        self.closeContext()
        self.Error.clear()
        data = None if data is None else Timeseries.from_data_table(data)
        if data is not None and not isinstance(data.time_variable, TimeVariable):
            self.Error.no_time_variable()
            data = None
        self.data = data
        if data is None:
            self.model.clear()
            self.commit()
            return
        self.set_default(self.data)
        self.openContext(self.data)
        self.unpack_settings()
        self.commit()

    def set_default(self, data):
        self.variables = [attr for attr in chain(data.domain.variables,
                                                 data.domain.metas)
                          if attr != data.time_variable]
        self.agg_funcs = [AGG_FUNCTIONS[0] if attr.is_continuous else
                          Mode if attr.is_discrete else
                          Concatenate if attr.is_string else None
                          for attr in self.variables]

    def pack_settings(self):
        self.variables = [i[0] for i in self.model.tolist()]
        self.agg_funcs = [i[1] for i in self.model.tolist()]

    def unpack_settings(self):
        self.model[:] = [[var, func] for var, func in zip(self.variables,
                                                          self.agg_funcs)]

    def commit(self):
        data = self.data
        if not data:
            self.Outputs.time_series.send(None)
            return

        # Group-by expects data sorted
        sorted_indices = np.argsort(data.time_values)
        if not np.all(sorted_indices == np.arange(len(data))):
            data = Timeseries.from_data_table(Table.from_table_rows(data, sorted_indices))

        attrs, cvars, metas = [], [], []
        for attr, _ in self.model:
            if attr in data.domain.attributes:
                attrs.append(attr)
            elif attr in data.domain.class_vars:
                cvars.append(attr)
            else:
                metas.append(attr)

        aggregate_time = self.AGG_TIME[self.agg_interval]

        def time_key(i):
            return timestamp(aggregate_time(fromtimestamp(data.time_values[i],
                                                           tz=data.time_variable.timezone)))

        times = []
        X, Y, M = [], [], []
        for key_time, indices in groupby(np.arange(len(data)), key=time_key):
            times.append(key_time)
            subset = data[list(indices)]

            xs, ys, ms = [], [], []
            for attr, func in self.model:
                values = Table.from_table(Domain([], [], [attr], source=data.domain), subset).metas
                out = (xs if attr in data.domain.attributes else
                       ys if attr in data.domain.class_vars else
                       ms)
                out.append(func(values))

            X.append(xs)
            Y.append(ys)
            M.append(ms)

        ts = Timeseries.from_numpy(
            Domain([data.time_variable] + attrs, cvars, metas),
            np.column_stack((times, np.row_stack(X))),
            np.array(Y),
            np.array(np.row_stack(M), dtype=object))
        self.Outputs.time_series.send(ts)


if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication

    a = QApplication([])
    ow = OWAggregate()
    ow.set_data(Timeseries.from_file('airpassengers'))

    ow.show()
    a.exec()
