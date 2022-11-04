from collections import Counter
from itertools import chain

import numpy as np

from AnyQt.QtCore import Qt, QSortFilterProxyModel, QRect
from AnyQt.QtWidgets import \
    QListView, QCheckBox, QLineEdit, QSizePolicy, QBoxLayout, QPushButton
from AnyQt.QtGui import QFont

from orangewidget.utils.widgetpreview import WidgetPreview

from Orange.data import Domain, Table, ContinuousVariable
import Orange.data.util
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.itemmodels import VariableListModel
from Orange.widgets.widget import Input, Output

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.aggregate import \
    PeriodOptions, AggOptions, time_blocks

N_NONPERIODIC = \
    next(iter(i for i, p in enumerate(PeriodOptions.values()) if p.periodic))


class TransformationsModel(VariableListModel):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._transformations = []

    def set_variables(self, variables):
        self[:] = variables
        self._transformations = [set() for _ in self]

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.FontRole and self._transformations[index.row()]:
            font = QFont()
            font.setBold(True)
            return font

        value = super().data(index, role)
        if role == Qt.DisplayRole:
            transformations = self.get_transformations(index)
            if transformations:
                value += ": " + ", ".join(transformations).lower()
        return value

    def get_transformations(self, index):
        # Don't just return the set: we want to have the same order for all!
        if not isinstance(index, int):
            index = index.row()
        return [trans for trans in AggOptions
                if trans in self._transformations[index]]

    def set_transformations(self, index, transformations):
        if not isinstance(index, int):
            index = index.row()
        self._transformations[index] = transformations.copy()

    def set_transformation(self, indexes, transformation, state):
        oper = set.add if state else set.discard
        rows = [index.row() for index in indexes]
        for row in rows:
            oper(self._transformations[row], transformation)
        self.dataChanged.emit(self.index(min(rows), 0), self.index(max(rows), 0))


class NumericFilterProxy(QSortFilterProxyModel):
    def __init__(self, source_model, filtering, pattern=""):
        super().__init__()
        self.setSourceModel(source_model)
        self.filtering = filtering
        self.pattern = pattern

    def set_filtering_numeric(self, filtering):
        self.filtering = filtering
        self.invalidateFilter()

    def set_pattern(self, pattern):
        self.pattern = pattern
        self.invalidateFilter()

    def filterAcceptsRow(self, row, _):
        var = self.sourceModel()[row]
        return (not self.filtering or var.is_continuous) \
            and (not self.pattern or self.pattern in var.name)


class OWMovingTransform(widget.OWWidget):
    name = 'Moving Transform'
    description = 'Apply rolling window functions to the time series.'
    icon = 'icons/MovingTransform.svg'
    priority = 20

    replaces = ["orangecontrib.timeseries.widgets.owaggregate.OWAggregate"]

    mainArea_width_height_ratio = None

    class Inputs:
        time_series = Input("Time series", Table)

    class Outputs:
        time_series = Output("Time series", Timeseries)

    class Warning(widget.OWWidget.Warning):
        no_aggregations = widget.Msg("No (applicable) aggregations are selected")
        inapplicable_aggregations = \
            widget.Msg("Some aggregations are applicable "
                       "only to sliding window ({})")
        window_to_large = widget.Msg("Window width is too large")
        block_to_large = widget.Msg("Block width is too large")

    class Error(widget.OWWidget.Error):
        migrated_aggregate = widget.Msg(
            "Aggregate was replaced with Moving Transform; "
            "manually re-set the widget")

    DiscardOriginal, KeepFirst, KeepMiddle, KeepLast = range(4)
    REF_OPTIONS = ("Discard original data", "Keep first instance",
                   "Keep middle instance", "Keep last instance")

    KeepComplete, KeepAll = range(1, 3)
    KEEP_OPTIONS = ("Discard original data",
                    "Keep original data",
                    "Include leading instances")
    KEEP_TOOLTIPS = ("Output data will contain only aggregates.",
                     "Output data will include original data instances,\n"
                     "except for the first N-1 (where N is window width).",
                     "Output data will include all original instances,\n"
                     "including the leading ones, for which the aggregate\n"
                     "is not computed.")

    SlidingWindow, SequentialBlocks, TimePeriods = range(3)

    method = settings.Setting(SlidingWindow)

    window_width = settings.Setting(5)
    keep_instances = settings.Setting(KeepComplete)

    block_width = settings.Setting(5)
    ref_instance = settings.Setting(DiscardOriginal)

    period_width = settings.Setting("Years")
    use_names = settings.Setting(True)

    var_hints = settings.Setting({}, schema_only=True)
    autocommit = settings.Setting(True)

    migrated_aggregate = settings.Setting(False)

    def __init__(self):
        self.data = None
        self.only_numeric = False

        self.mainArea.layout().setDirection(QBoxLayout.LeftToRight)
        box = gui.hBox(self.controlArea, True)

        vbox = gui.vBox(box, "Aggregation Type")
        buttons = gui.radioButtons(
            vbox, self, "method", callback=self._method_changed)

        gui.appendRadioButton(buttons, "Sliding window")
        indbox = gui.indentedBox(buttons)
        gui.spin(
            indbox, self, 'window_width',
            2, 1000, label='Window width:',
            controlWidth=80, alignment=Qt.AlignRight,
            callback=self._window_width_changed)
        cb = gui.comboBox(
            indbox, self, "keep_instances", items=self.KEEP_OPTIONS,
            sizePolicy=(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed),
            callback=self._keep_instances_changed)
        for i, tip in enumerate(self.KEEP_TOOLTIPS):
            cb.setItemData(i, tip, Qt.ToolTipRole)
        cb.setToolTip(self.KEEP_TOOLTIPS[self.keep_instances])
        gui.separator(buttons)

        gui.appendRadioButton(buttons, "Consecutive blocks", buttons)
        indbox = gui.indentedBox(buttons)
        gui.spin(
            indbox, self, 'block_width',
            2, 1000, label='Block width:',
            controlWidth=80, alignment=Qt.AlignRight,
            callback=self._use_sequential_blocks)
        gui.comboBox(
            indbox, self, "ref_instance", items=self.REF_OPTIONS,
            sizePolicy=(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed),
            callback=self._use_sequential_blocks
        )
        gui.separator(buttons)

        self.rb_period = gui.appendRadioButton(
            buttons, "Aggregate time periods", buttons)
        indbox = gui.indentedBox(buttons)
        cb = gui.comboBox(
            indbox, self, "period_width",
            items=list(PeriodOptions), sendSelectedValue=True,
            sizePolicy=(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed),
            callback=self._time_period_changed
        )
        cb.insertSeparator(N_NONPERIODIC)
        gui.checkBox(indbox, self, "use_names", "",
                     callback=self.commit.deferred).setVisible(False)

        gui.rubber(buttons)

        vbox = gui.vBox(self.mainArea, True)
        self.filter_line = QLineEdit(placeholderText="Filter ...")
        self.filter_line.textEdited.connect(self._filter_changed)
        self.filter_line.setAttribute(Qt.WA_MacShowFocusRect, False)

        self.clear_filter = QPushButton("✕", self.filter_line)
        self.clear_filter.setFixedWidth(30)
        self.clear_filter.setAutoDefault(False)
        self.clear_filter.setFlat(True)
        self.clear_filter.setHidden(True)
        self.clear_filter.clicked.connect(self._clear_filter)

        vbox.layout().addWidget(self.filter_line)
        self.var_view = view = QListView()
        self.var_model = TransformationsModel(parent=self)
        self.proxy = NumericFilterProxy(self.var_model, self.only_numeric)
        view.setModel(self.proxy)
        view.setSelectionMode(QListView.ExtendedSelection)
        view.selectionModel().selectionChanged.connect(self._selection_changed)
        view.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        vbox.layout().addWidget(view)
        gui.checkBox(vbox, self, "only_numeric", "Show only numeric variables",
                     callback=self._show_numeric_changed)

        cbox = gui.vBox(self.mainArea)
        for agg in AggOptions.values():
            cb = QCheckBox(agg.long_desc)
            cb.setObjectName(agg.short_desc)
            cb.clicked.connect(self._checkbox_changed)
            cbox.layout().addWidget(cb)

        gui.auto_commit(self.buttonsArea, self, 'autocommit', '&Apply')

    def resizeEvent(self, event):
        self._set_clear_filter_pos()

    def _set_clear_filter_pos(self):
        parrect = self.filter_line.size()
        size = self.clear_filter.sizeHint()
        rect = QRect(
            parrect.width() - 30, (parrect.height() - size.height()) // 2,
            30, size.height())
        self.clear_filter.setGeometry(rect)

    def _clear_filter(self):
        self.filter_line.clear()
        self._filter_changed()

    def _method_changed(self):
        self._hide_migrated_aggregate()
        self.commit.deferred()

    def _window_width_changed(self):
        self.method = self.SlidingWindow
        self._hide_migrated_aggregate()
        self.commit.deferred()

    def _keep_instances_changed(self):
        self.method = self.SlidingWindow
        self._hide_migrated_aggregate()
        self.controls.keep_instances.setToolTip(
            self.KEEP_TOOLTIPS[self.keep_instances])
        self.commit.deferred()

    def _use_sequential_blocks(self):
        self.method = self.SequentialBlocks
        self._hide_migrated_aggregate()
        self.commit.deferred()

    def _time_period_changed(self):
        self.method = self.TimePeriods
        self._set_naming_visibility()
        self.commit.deferred()

    def _set_naming_visibility(self):
        period = PeriodOptions[self.period_width]
        visible = self.method == self.TimePeriods and period.names is not None
        cb = self.controls.use_names
        if visible:
            cb.setText(period.names_option)
        cb.setVisible(visible)

    def _show_numeric_changed(self):
        self.proxy.set_filtering_numeric(self.only_numeric)

    def _filter_changed(self):
        self._set_clear_filter_pos()
        text = self.filter_line.text()
        self.clear_filter.setHidden(not text)
        self.proxy.set_pattern(text)

    def _current_selection(self):
        return self.proxy.mapSelectionToSource(
            self.var_view.selectionModel().selection()).indexes()

    @staticmethod
    def _varkey(var):
        return var.name, var.is_continuous

    def _checkbox_changed(self):
        state = self.sender().isChecked()
        transformation = self.sender().objectName()
        selection = self._current_selection()
        self.var_model.set_transformation(selection, transformation, state)
        self.var_view.setFocus()
        for index in selection:
            key = self._varkey(self.var_model[index.row()])
            transfs = self.var_model.get_transformations(index)
            if transfs:
                self.var_hints[key] = set(transfs)
            elif key in self.var_hints:
                del self.var_hints[key]

        self._hide_migrated_aggregate()
        self.commit.deferred()

    def _selection_changed(self):
        selection = self._current_selection()
        nselected = len(selection)
        model = self.var_model
        counts = Counter(chain(*map(model.get_transformations, selection)))
        disc = any(self.var_model[index.row()].is_discrete
                   for index in selection)
        for trans, desc in AggOptions.items():
            cb = self.findChild(QCheckBox, trans)
            cb.setCheckState(
                Qt.Unchecked if trans not in counts else
                Qt.PartiallyChecked if counts[trans] < nselected else
                Qt.Checked)
            cb.setDisabled(not nselected or disc and not desc.supports_discrete)

    @Inputs.time_series
    def set_data(self, data):
        if data is None:
            self.data = None
            self.var_model.set_variables([])
        else:
            self.data = Timeseries.from_data_table(data)
            self.var_model.set_variables(
                var for var in self.data.domain.variables
                if var.is_discrete or
                var.is_continuous and var is not self.data.time_variable)
            for i, attr in enumerate(self.var_model):
                transformations = self.var_hints.get(self._varkey(attr))
                if transformations:
                    self.var_model.set_transformations(i, transformations)

        disabled = self.data is not None and self.data.time_variable is None
        self.rb_period.setDisabled(disabled)
        self.controls.period_width.setDisabled(disabled)

        self._selection_changed()
        self._set_naming_visibility()
        self.commit.now()

    @gui.deferred
    def commit(self):
        self.Warning.clear()
        self.Error.clear()

        if not self.data:
            ts = None
        elif self.migrated_aggregate:
            self.Error.migrated_aggregate()
            ts = None
        else:
            ts = [self._compute_sliding_window,
                  self._compute_sequential_blocks,
                  self._compute_period_aggregation][self.method]()
        self.Outputs.time_series.send(ts)

    def _compute_sliding_window(self):
        data = self.data
        domain = data.domain
        model = self.var_model
        discard = self.keep_instances == self.DiscardOriginal
        self.Warning.window_to_large(shown=self.window_width > len(data))

        names = [f"{var.name} ({trans})"
                 for i, var in enumerate(model)
                 for trans in model.get_transformations(i)]
        if discard:
            names = iter(Orange.data.util.get_unique_names([], names))
        else:
            names = iter(Orange.data.util.get_unique_names(domain, names))

        attributes = []
        columns = []
        if discard:
            rows = leading = None
        elif self.keep_instances == self.KeepComplete:
            rows = slice(self.window_width - 1, None)
            leading = None
        else:
            rows = ...
            leading = np.full(self.window_width - 1, np.nan)

        def add_aggregates(attr, column):
            if attr not in model:  # skip time_attribute
                return
            row = model.indexOf(attr)
            for transformation in model.get_transformations(row):
                agg = AggOptions[transformation]
                attributes.append(self._var_for_agg(attr, agg, names))
                if agg.cumulative and self.keep_instances == self.KeepAll:
                    agg_column = agg.cumulative(column)
                else:
                    agg_column = agg.transform(column, self.window_width, 1)
                    if self.keep_instances == self.KeepAll:
                        agg_column = np.hstack((leading, agg_column))
                columns.append(agg_column)

        for attr, column in zip(domain.attributes, data.X.T):
            if not discard:
                attributes.append(attr)
                columns.append(column[rows])
            add_aggregates(attr, column)
        for attr, column in zip(domain.class_vars,
                                [data.Y] if data.Y.ndim == 1 else data.Y.T):
            add_aggregates(attr, column)

        self._set_warnings(columns, None)
        if not columns:
            return None

        x = np.vstack(columns).T
        if discard:
            domain = Domain(attributes)
            return Timeseries.from_numpy(
                domain, x, attributes=data.attributes)
        else:
            domain = Domain(attributes, domain.class_vars, domain.metas)
            return Timeseries.from_numpy(
                domain, x, data.Y[rows], data.metas[rows], data.W[rows],
                data.attributes, ids=data.ids[rows]
            )

    def _compute_sequential_blocks(self):
        data = self.data
        domain = data.domain
        model = self.var_model
        width = self.block_width
        if width > len(data):
            self.Warning.block_to_large()
            return None

        def add_aggregates(attr, column=None):
            if attr not in model:  # skip time_attribute
                return
            row = model.indexOf(attr)
            for transformation in model.get_transformations(row):
                agg = AggOptions[transformation]
                if agg.block_transform is None:
                    inapplicable.add(agg.long_desc)
                    continue
                if column is None:
                    column = data.get_column(attr)
                agg_column = agg.transform(column, width, width)
                attributes.append(self._var_for_agg(attr, agg, names))
                columns.append(agg_column)

        names = self._names_for_blocked_aggregation()
        attributes = []
        columns = []
        inapplicable = set()
        rows = {self.DiscardOriginal: slice(0, 0),
                self.KeepFirst: slice(0, -(width - 1), width),
                self.KeepMiddle: slice(width // 2, -(width - 1 - width // 2), width),
                self.KeepLast: slice(width - 1, None, width)
                }[self.ref_instance]
        for attr, column in zip(domain.attributes, data.X.T):
            if self.ref_instance != self.DiscardOriginal:
                attributes.append(attr)
                columns.append(column[rows])
            add_aggregates(attr, column)
        for attr in domain.class_vars:
            add_aggregates(attr)
        self._set_warnings(columns, inapplicable)
        if not columns:
            return None

        x = np.vstack(columns).T
        if self.ref_instance == self.DiscardOriginal:
            return Timeseries.from_numpy(Domain(attributes), x)
        else:
            new_domain = Domain(attributes, domain.class_vars, domain.metas)
            return Timeseries.from_numpy(
                new_domain, x, data.Y[rows], data.metas[rows], data.W[rows],
                data.attributes, ids=data.ids[rows]
            )

    def _compute_period_aggregation(self):
        data = self.data
        model = self.var_model

        names = self._names_for_blocked_aggregation()
        period = PeriodOptions[self.period_width]

        attributes = []
        columns = []
        attribute, periods, period_indices, counts = \
            time_blocks(data, period, next(names), self.use_names)
        attributes.append(attribute)
        columns.append(periods)

        attributes.append(ContinuousVariable(next(names)))
        columns.append(counts)

        inapplicable = set()
        for i, attr in enumerate(model):
            for transformation in model.get_transformations(i):
                agg = AggOptions[transformation]
                if agg.block_transform is None:
                    inapplicable.add(agg.long_desc)
                    continue
                attributes.append(self._var_for_agg(attr, agg, names))
                column = data.get_column(attr)
                agg_column = np.array([
                    agg.block_transform(column[period_indices == i])
                    for i in range(len(periods))])
                columns.append(agg_column)

        self._set_warnings(columns, inapplicable)
        if not columns:
            return None
        return Timeseries.from_numpy(Domain(attributes), np.vstack(columns).T)

    def _names_for_blocked_aggregation(self):
        # Sequential blocks do not use `block_transform` function, but the
        # presence of this function indicates that the aggregations is
        # applicable to sequential blocks
        model = self.var_model
        domain = self.data.domain

        names = []
        if self.method == self.TimePeriods:
            names += [self.period_width, "Instance count"]
        names += [f"{var.name} ({trans})"
                  for i, var in enumerate(model)
                  for trans in model.get_transformations(i)
                  if AggOptions[trans].block_transform]
        if self.method == self.SequentialBlocks \
                and self.ref_instance != self.DiscardOriginal:
            names = Orange.data.util.get_unique_names(domain, names)
        else:
            names = Orange.data.util.get_unique_names_duplicates(names)
        return iter(names)

    @staticmethod
    def _var_for_agg(attr, agg, names):
        name = next(names)
        if agg.count_aggregate:
            return ContinuousVariable(name, number_of_decimals=0)
        return attr.copy(name=name)

    def _set_warnings(self, columns, inapplicable):
        if inapplicable:
            self.Warning.inapplicable_aggregations(
                ", ".join(agg.long_desc for agg in AggOptions.values()
                          if agg.long_desc in inapplicable)
            )
        if not columns:
            self.Warning.no_aggregations()

    def send_report(self):
        if self.method == self.SlidingWindow:
            self.report_items(
                "Sliding Window",
                (("Window width", self.window_width),
                 ("Original data", self.KEEP_OPTIONS[self.keep_instances].lower())))
        elif self.method == self.SequentialBlocks:
            self.report_items(
                "Consecutive blocks",
                (("Block width", self.block_width),
                 ("Original data", self.REF_OPTIONS[self.ref_instance].lower())))
        else:
            assert self.method == self.TimePeriods
            self.report_items(
                "Aggregate time periods",
                (("Period", self.period_width), )
            )

        model = self.var_model
        transformations = []
        for i, attr in enumerate(model):
            transfs = model.get_transformations(i)
            if self.method != self.SlidingWindow:
                transfs = [t for t in transfs
                           if AggOptions[t].block_transform is not None]
            if transfs:
                transformations.append(
                    (attr.name,
                     ", ".join(AggOptions[t].long_desc for t in transfs)))
        if transformations:
            self.report_items("Transformations", tuple(transformations))

    @classmethod
    def migrate_settings(cls, settings, _=None):
        if "agg_interval" in settings:
            for name in ("agg_interval", "agg_funcs",
                         "savedWidgetGeometry", "context_settings"):
                if name in settings:
                    del settings[name]
            settings["migrated_aggregate"] = True

    def _hide_migrated_aggregate(self):
        self.migrated_aggregate = False
        self.Error.migrated_aggregate.clear()


if __name__ == "__main__":
    # data = Timeseries.from_file('heart_disease')
    data = Timeseries.from_file('airpassengers')
    # data = Timeseries.from_file('/Users/janez/Downloads/slovenia-traffic-accidents-2016-events.tab')
    attrs = [var.name for var in data.domain.attributes]
    if 'Adj Close' in attrs:
        # Make Adjusted Close a class variable
        attrs.remove('Adj Close')
        data = Timeseries.from_table(
            Domain(attrs, [data.domain['Adj Close']], None, source=data.domain),
            data)
    WidgetPreview(OWMovingTransform).run(data)
