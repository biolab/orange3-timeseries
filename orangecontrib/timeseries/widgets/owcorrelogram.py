from typing import List

import numpy as np

from AnyQt.QtCore import QItemSelectionModel, Qt, QTimer, QItemSelection
from AnyQt.QtWidgets import QListView

import pyqtgraph as pg

from orangewidget.settings import Setting
from orangewidget.utils.widgetpreview import WidgetPreview

from Orange.data import Table, ContinuousVariable
from Orange.widgets import widget, gui
from Orange.widgets.utils.colorpalettes import DefaultDiscretePalette, Glasbey
from Orange.widgets.utils.itemmodels import VariableListModel
from Orange.widgets.widget import Input

from orangecontrib.timeseries import (
    Timeseries, autocorrelation, partial_autocorrelation)


class OWCorrelogram(widget.OWWidget):
    # TODO: allow computing cross-correlation of two distinct series
    name = 'Correlogram'
    description = "Visualize variables' auto-correlation."
    icon = 'icons/Correlogram.svg'
    priority = 110

    class Inputs:
        time_series = Input("Time series", Table)

    # Selected attributes are stored as strings. They are always continuous,
    # so there's nothing to match, and storing as Variable would require
    # context handler.
    use_pacf = Setting(False)
    use_confint = Setting(True)
    selection: List[str] = Setting([], schema_only=True)

    graph_name = 'plot'

    class Error(widget.OWWidget.Error):
        no_instances = widget.Msg("Data contains just a single instance")
        no_variables = widget.Msg("Data doesn't contain any numeric variables")

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

        gui.separator(self.controlArea)
        gui.checkBox(self.controlArea, self, 'use_pacf',
                     label='Compute partial auto-correlation',
                     callback=self.replot)
        gui.checkBox(self.controlArea, self, 'use_confint',
                     label='Plot 95% significance interval',
                     callback=self.replot)

        self.plot_widget = pg.PlotWidget(background="w")
        self.plot = self.plot_widget.getPlotItem()
        self.plot.setYRange(-1, 1)
        self.plot.buttonsHidden = False
        self.plot.vb.setMouseEnabled(x=True, y=False)
        self.mainArea.layout().addWidget(self.plot_widget)
        self.plot.sigYRangeChanged.connect(self._rescale_y)

    def _rescale_y(self):
        QTimer.singleShot(1, lambda: self.plot.setYRange(-1, 1))

    def acf(self, attr, pacf, confint):
        if attr not in self._cached:
            x = self.data.interp(attr).ravel()
            func = partial_autocorrelation if pacf else autocorrelation
            self._cached[attr] = func(x, alpha=.05 if confint else None)
        return self._cached[attr]

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
        self.replot()

    def replot(self):
        self.plot.clear()
        if not self.selection:
            return

        palette = DefaultDiscretePalette
        if len(self.selection) > len(palette):
            palette = Glasbey

        self.plot_widget.addItem(pg.InfiniteLine(0, 0, pen=pg.mkPen(0., width=2)))

        for i, attr in enumerate(self.selection):
            color = palette.value_to_qcolor(i)
            x, acf = np.array(self.acf(attr, self.use_pacf, False)).T
            x = np.repeat(x, 2)
            y = np.vstack((np.zeros(len(acf)), acf)).T.flatten()
            item = pg.PlotCurveItem(
                x=x, y=y, connect="pairs", antialias=True,
                pen=pg.mkPen(color, width=5))
            self.plot_widget.addItem(item)

            if self.use_confint:
                # Confidence intervals, from:
                # https://www.mathworks.com/help/econ/autocorrelation-and-partial-autocorrelation.html
                # https://www.mathworks.com/help/signal/ug/confidence-intervals-for-sample-autocorrelation.html
                se = np.sqrt((1 + 2 * (acf ** 2).sum()) / len(self.data))
                std = 1.96 * se
                pen = pg.mkPen(color, width=2, style=Qt.DashLine)
                self.plot_widget.addItem(pg.InfiniteLine(std, 0, pen=pen))
                self.plot_widget.addItem(pg.InfiniteLine(-std, 0, pen=pen))


if __name__ == "__main__":
    WidgetPreview(OWCorrelogram).run(
        Timeseries.from_file("airpassengers")
    )
