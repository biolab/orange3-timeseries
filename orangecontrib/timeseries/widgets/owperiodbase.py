from html import escape
from typing import List

from AnyQt.QtCore import QItemSelectionModel, QTimer, QItemSelection
from AnyQt.QtWidgets import QListView

import pyqtgraph as pg

from orangecontrib.timeseries import Timeseries
from orangewidget.settings import Setting

from Orange.data import Table, ContinuousVariable
from Orange.widgets.utils.itemmodels import VariableListModel
from Orange.widgets.widget import OWWidget, Input, Msg
from Orange.widgets.utils.colorpalettes import DefaultDiscretePalette, Glasbey
from Orange.widgets.visualize.owdistributions import LegendItem


class OWPeriodBase(OWWidget, openclass=True):
    class Inputs:
        time_series = Input("Time series", Table)

    # Selected attributes are stored as strings. They are always continuous,
    # so there's nothing to match, and storing as Variable would require
    # context handler.
    selection: List[str] = Setting([], schema_only=True)

    graph_name = 'plot'

    class Error(OWWidget.Error):
        no_instances = Msg("Data contains just a single instance")
        no_variables = Msg("Data doesn't contain any numeric variables")

    def __init__(self):
        self.data = None
        self.model = VariableListModel()
        self._cached = {}
        self.persistent_selection = self.selection

        listbox = QListView(self)
        listbox.setModel(self.model)
        self.controlArea.layout().addWidget(listbox)

        self.selectionModel = listbox.selectionModel()
        self.selectionModel.selectionChanged.connect(self._selection_changed)
        listbox.setSelectionModel(self.selectionModel)
        listbox.setSelectionMode(QListView.ExtendedSelection)

        self.plot_widget = pg.PlotWidget(background="w")
        self.plot = self.plot_widget.getPlotItem()
        self.plot.showGrid(x=False, y=True)
        self.plot.setYRange(*self.yrange)
        self.plot.buttonsHidden = False
        self.plot.vb.setMouseEnabled(x=True, y=False)
        self.mainArea.layout().addWidget(self.plot_widget)
        self.plot.sigYRangeChanged.connect(self._rescale_y)

        self.legend = self._create_legend(((1, 0), (1, 0)))

    def _create_legend(self, anchor):
        legend = LegendItem()
        legend.setLabelTextSize("12pt")
        legend.setParentItem(self.plot.vb)
        legend.restoreAnchor(anchor)
        legend.hide()
        return legend

    def update_legend(self):
        self.legend.clear()
        if not self.selection:
            self.legend.hide()
            return

        for name, color in zip(self.selection, self.get_palette()):
            dot = pg.ScatterPlotItem(pen=color, brush=color, size=10, shape="s")
            self.legend.addItem(dot, escape(name))
        self.legend.show()

    @staticmethod
    def time_scale(span):
        for secs, unit in ((31556952, "years"),  # Gregorian year
                           # we can't have month - not well defined
                           (24 * 3600, "days"),
                           (3600, "hours"),
                           (60, "minutes")):
            if span > 10 * secs:
                return secs, unit
        return 1, "seconds"

    def _rescale_y(self):
        QTimer.singleShot(1, lambda: self.plot.setYRange(*self.yrange))

    @Inputs.time_series
    def set_data(self, data):
        self.plot.clear()
        self._cached.clear()
        self.Error.clear()

        if self.selection:
            self.persistent_selection = self.selection[:]

        if not data or len(data) < 2:
            self.Error.no_instances(shown=bool(data))
            self.data = None
            self.model.clear()
            return

        self.data = Timeseries.from_data_table(data)
        self.model[:] = [
            var for var in self.data.domain.variables
            if isinstance(var, ContinuousVariable)
               and var is not self.data.time_variable]
        if not self.model:
            self.Error.no_variables()
            self.data = None
            return

        item_selection = QItemSelection()
        names = [attr.name for attr in self.model]
        selection = [
            names.index(name)
            for name in self.persistent_selection
            if name in names]
        for idx in selection or [0]:
            index = self.model.index(idx)
            item_selection.select(index, index)
        self.selectionModel.select(item_selection,
                                   QItemSelectionModel.ClearAndSelect)

    def _selection_changed(self):
        self.selection = [
            self.model.data(index)
            for index in self.selectionModel.selectedIndexes()]
        self.update_legend()
        self.replot()

    def get_palette(self):
        if len(self.selection) > len(DefaultDiscretePalette):
            return Glasbey
        return DefaultDiscretePalette
