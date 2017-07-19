from AnyQt.QtCore import Qt, QSize
from AnyQt.QtWidgets import QStyledItemDelegate, QComboBox, QSpinBox
from AnyQt.QtGui import QIcon

from Orange.data import Domain, Table
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.itemmodels import VariableListModel, PyTableModel

from orangecontrib.timeseries.widgets.utils import ListModel
from orangecontrib.timeseries import Timeseries, moving_transform
from orangecontrib.timeseries.agg_funcs import AGG_FUNCTIONS, Mean, Cumulative_sum, Cumulative_product


class Output:
    TIMESERIES = 'Time series'


class OWMovingTransform(widget.OWWidget):
    name = 'Moving Transform'
    description = 'Apply rolling window functions to the time series.'
    icon = 'icons/MovingTransform.svg'
    priority = 20

    inputs = [("Time series", Table, 'set_data')]
    outputs = [("Time series", Timeseries)]

    want_main_area = False

    non_overlapping = settings.Setting(False)
    fixed_wlen = settings.Setting(5)
    transformations = settings.Setting([])
    autocommit = settings.Setting(False)
    last_win_width = settings.Setting(5)

    _NON_OVERLAPPING_WINDOWS = 'Non-overlapping windows'

    UserAdviceMessages = [
        widget.Message('Get the simple moving average (SMA) of a series '
                       'by setting the aggregation function to "{}".'.format(Mean),
                       'sma-is-mean'),
        widget.Message('If "{}" is checked, the rolling windows don\t '
                       'overlap. Instead, they run through the series '
                       'side-to-side, so the resulting transformed series is '
                       'fixed-window-length-times shorter.'.format(_NON_OVERLAPPING_WINDOWS),
                       'non-overlapping')
    ]

    def __init__(self):
        self.data = None
        box = gui.vBox(self.controlArea, 'Moving Transform')

        def _disable_fixed_wlen():
            fixed_wlen.setDisabled(not self.non_overlapping)
            self.view.repaint()
            self.on_changed()

        gui.checkBox(box, self, 'non_overlapping',
                     label=self._NON_OVERLAPPING_WINDOWS,
                     callback=_disable_fixed_wlen,
                     tooltip='If this is checked, instead of rolling windows '
                             'through the series, they are applied side-to-side, '
                             'so the resulting output series will be some '
                             'length-of-fixed-window-times shorter.')
        fixed_wlen = gui.spin(box, self, 'fixed_wlen', 2, 1000,
                              label='Fixed window width:',
                              callback=self.on_changed)
        fixed_wlen.setDisabled(not self.non_overlapping)
        # TODO: allow the user to choose left-aligned, right-aligned, or center-aligned window

        class TableView(gui.TableView):
            def __init__(self, parent):
                super().__init__(parent,
                                 editTriggers=(self.SelectedClicked |
                                               self.CurrentChanged |
                                               self.DoubleClicked |
                                               self.EditKeyPressed),
                                 )
                self.horizontalHeader().setStretchLastSection(False)
                agg_functions = ListModel(AGG_FUNCTIONS +
                                          [Cumulative_sum, Cumulative_product],
                                          parent=self)
                self.setItemDelegateForColumn(0, self.VariableDelegate(parent))
                self.setItemDelegateForColumn(1, self.SpinDelegate(parent))
                self.setItemDelegateForColumn(2, self.ComboDelegate(self, agg_functions))

            class _ItemDelegate(QStyledItemDelegate):
                def updateEditorGeometry(self, widget, option, _index):
                    widget.setGeometry(option.rect)

            class ComboDelegate(_ItemDelegate):
                def __init__(self, parent=None, combo_model=None):
                    super().__init__(parent)
                    self._parent = parent
                    if combo_model is not None:
                        self._combo_model = combo_model

                def createEditor(self, parent, _QStyleOptionViewItem, index):
                    combo = QComboBox(parent)
                    combo.setModel(self._combo_model)
                    return combo

                def setEditorData(self, combo, index):
                    var = index.model().data(index, Qt.EditRole)
                    combo.setCurrentIndex(self._combo_model.indexOf(var))

                def setModelData(self, combo, model, index):
                    var = self._combo_model[combo.currentIndex()]
                    model.setData(index, var, Qt.EditRole)

            class VariableDelegate(ComboDelegate):
                @property
                def _combo_model(self):
                    return self._parent.var_model

            class SpinDelegate(_ItemDelegate):
                def paint(self, painter, option, index):
                    # Don't paint window length if non-overlapping windows set
                    if not self.parent().non_overlapping:
                        super().paint(painter, option, index)

                def createEditor(self, parent, _QStyleOptionViewItem, _index):
                    # Don't edit window length if non-overlapping windows set
                    if self.parent().non_overlapping:
                        return None
                    spin = QSpinBox(parent, minimum=1, maximum=1000)
                    return spin

                def setEditorData(self, spin, index):
                    spin.setValue(index.model().data(index, Qt.EditRole))

                def setModelData(self, spin, model, index):
                    spin.interpretText()
                    model.setData(index, spin.value(), Qt.EditRole)

        self.var_model = VariableListModel(parent=self)

        self.table_model = model = PyTableModel(self.transformations,
                                                parent=self, editable=True)
        model.setHorizontalHeaderLabels(['Series', 'Window width', 'Aggregation function'])
        model.dataChanged.connect(self.on_changed)

        self.view = view = TableView(self)
        view.setModel(model)
        box.layout().addWidget(view)

        hbox = gui.hBox(box)
        from os.path import dirname, join
        self.add_button = button = gui.button(
            hbox, self, 'Add &Transform',
            callback=self.on_add_transform)
        button.setIcon(QIcon(join(dirname(__file__), 'icons', 'LineChart-plus.png')))

        self.del_button = button = gui.button(
            hbox, self, '&Delete Selected',
            callback=self.on_del_transform)
        QIcon.setThemeName('gnome')  # Works for me
        button.setIcon(QIcon.fromTheme('edit-delete'))

        gui.auto_commit(box, self, 'autocommit', '&Apply')

    def sizeHint(self):
        return QSize(450, 600)

    def on_add_transform(self):
        if self.data is not None:
            self.table_model.append([self.var_model[0], self.last_win_width, AGG_FUNCTIONS[0]])
        self.commit()

    def on_del_transform(self):
        for row in sorted([mi.row() for mi in self.view.selectionModel().selectedRows(0)],
                          reverse=True):
            del self.table_model[row]
        if len(self.table_model):
            selection_model = self.view.selectionModel()
            selection_model.select(self.table_model.index(len(self.table_model) - 1, 0),
                                   selection_model.Select | selection_model.Rows)
        self.commit()

    def set_data(self, data):
        self.data = data = None if data is None else Timeseries.from_data_table(data)
        self.add_button.setDisabled(not len(getattr(data, 'domain', ())))
        self.table_model.clear()
        if data is not None:
            self.var_model.wrap([var for var in data.domain
                                 if var.is_continuous and var is not data.time_variable])
        self.on_changed()

    def on_changed(self):
        self.commit()

    def commit(self):
        data = self.data
        if not data:
            self.send(Output.TIMESERIES, None)
            return

        ts = moving_transform(data, self.table_model, self.non_overlapping and self.fixed_wlen)
        self.send(Output.TIMESERIES, ts)


if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication

    a = QApplication([])
    ow = OWMovingTransform()

    data = Timeseries('yahoo_MSFT')
    attrs = [var.name for var in data.domain.attributes]
    if 'Adj Close' in attrs:
        # Make Adjusted Close a class variable
        attrs.remove('Adj Close')
        data = Timeseries(Domain(attrs, [data.domain['Adj Close']], None, source=data.domain), data)

    ow.set_data(data)

    ow.show()
    a.exec()
