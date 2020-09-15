from AnyQt.QtCore import Qt, QSize
from AnyQt.QtWidgets import QStyledItemDelegate, QComboBox, QSpinBox
from AnyQt.QtGui import QIcon

from Orange.data import Domain, Table
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.itemmodels import VariableListModel, PyTableModel
from Orange.widgets.widget import Input, Output, Msg, OWWidget

from orangecontrib.timeseries.widgets.utils import ListModel
from orangecontrib.timeseries import Timeseries, moving_transform
from orangecontrib.timeseries.agg_funcs import AGG_FUNCTIONS, Mean, Cumulative_sum, Cumulative_product
from orangewidget.settings import _apply_setting
from orangewidget.utils.widgetpreview import WidgetPreview


class MovingTransformContextHandler(settings.ContextHandler):
    rev_agg_functions = {func.__name__: func for func in AGG_FUNCTIONS}

    def new_context(self, variables, encoded_vars):
        context = super().new_context()
        context.encoded_vars = vars
        return context

    def open_context(self, widget, variables):
        encoded_vars = settings.DomainContextHandler.encode_variables(
            variables, False)
        super().open_context(widget, variables, encoded_vars)

    def settings_to_widget(self, widget, variables, encoded_vars, *args):
        # TODO: If https://github.com/biolab/orange-widget-base/pull/56 is:
        #  - merged, remove this method.
        #  - rejected, remove this comment.
        context = widget.current_context
        if context is None:
            return

        widget.retrieveSpecificSettings()

        for setting, data, instance in \
                self.provider.traverse_settings(data=context.values, instance=widget):
            if not isinstance(setting, settings.ContextSetting) \
                    or setting.name not in data:
                continue

            value = self.decode_setting(setting, data[setting.name],
                                        variables, encoded_vars)
            _apply_setting(setting, instance, value)

    def encode_setting(self, context, setting, value):
        encode_variable = settings.DomainContextHandler.encode_variable
        return [[encode_variable(var), w_size, agg.__name__]
                for var, w_size, agg in value]

    def decode_setting(self, setting, value, variables, encoded_vars):
        if setting.name == "transformations":
            var_dict = {var.name: var for var in variables}
            return [[var_dict[name], w_size, self.rev_agg_functions[func]]
                    for (name, _), w_size, func in value]
        else:
            return super().decode_setting(self, setting, value)

    def match(self, context, variables, encoded_vars):
        transformations = context.values["transformations"]
        if transformations and all(encoded_vars.get(name) == tpe - 100
                                   for (name, tpe), *_ in transformations):
            return self.PERFECT_MATCH
        return self.NO_MATCH


class OWMovingTransform(widget.OWWidget):
    name = 'Moving Transform'
    description = 'Apply rolling window functions to the time series.'
    icon = 'icons/MovingTransform.svg'
    priority = 20

    class Inputs:
        time_series = Input("Time series", Table)

    class Outputs:
        time_series = Output("Time series", Timeseries)

    want_main_area = False

    settingsHandler = MovingTransformContextHandler()
    non_overlapping = settings.Setting(False)
    fixed_wlen = settings.Setting(5)
    transformations = settings.ContextSetting([])
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

    class Warning(OWWidget.Warning):
        no_transforms_added = Msg("At least one transform should be added.")

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

        self.table_model = model = PyTableModel(parent=self, editable=True)
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

        self.settingsAboutToBePacked.connect(self.store_transformations)

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

    def store_transformations(self):
        self.transformations = list(self.table_model)

    @Inputs.time_series
    def set_data(self, data):
        self.store_transformations()
        self.closeContext()
        self.transformations = []
        if data is None:
            self.data = None
            self.var_model.clear()
        else:
            self.data = Timeseries.from_data_table(data)
            self.var_model[:] = [
                var for var in self.data.domain.variables
                if var.is_continuous and var is not self.data.time_variable]

        self.add_button.setDisabled(not self.var_model)
        self.openContext(self.var_model)
        self.table_model[:] = self.transformations
        self.on_changed()

    def on_changed(self):
        self.commit()

    def commit(self):
        self.Warning.no_transforms_added.clear()
        data = self.data
        if not data:
            self.Outputs.time_series.send(None)
            return

        if not len(self.table_model):
            self.Warning.no_transforms_added()
            self.Outputs.time_series.send(None)
            return

        ts = moving_transform(data, self.table_model, self.non_overlapping and self.fixed_wlen)
        self.Outputs.time_series.send(ts)


if __name__ == "__main__":
    data = Timeseries.from_file('airpassengers')
    attrs = [var.name for var in data.domain.attributes]
    if 'Adj Close' in attrs:
        # Make Adjusted Close a class variable
        attrs.remove('Adj Close')
        data = Timeseries.from_table(
            Domain(attrs, [data.domain['Adj Close']], None, source=data.domain),
            data)
    WidgetPreview(OWMovingTransform).run(data)
