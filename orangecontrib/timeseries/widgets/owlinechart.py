from collections import OrderedDict

from functools import lru_cache
from sklearn.utils.fixes import partial

from Orange.data import ContinuousVariable
from Orange.util import scale
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.colorpalette import ColorPaletteGenerator

import pyqtgraph as pg
from pyqtgraph.dockarea import Dock, DockArea
from pyqtgraph.dockarea.DockDrop import DockDrop
from PyQt4.QtGui import QTreeWidget, QTreeWidgetItem, QFont, QSizePolicy
from PyQt4.QtCore import Qt, QSize

from orangecontrib.timeseries.widgets.owperiodogram import PlotWidget
from orangecontrib.timeseries import (
    Timeseries,
)

class OverviewPlot(pg.PlotWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

    def sizeHint(self):
        return QSize(2**23, 200)


class DockArea(DockArea):
    def __init__(self, *args, **kwargs):
        super().__init__(args, **kwargs)
        DockDrop.__init__(self, allowedAreas=['top', 'bottom'])


class Dock(Dock):
    def __init__(self, name, widget):
        super().__init__(name, area='left', widget=widget, closable=True)


class OWLineChart(widget.OWWidget):
    name = 'Line chart'
    description = "Visualize time series' progression."
    icon = 'icons/LineChart.svg'
    priority = 90

    inputs = [("Time series", Timeseries, 'set_data', widget.Multiple)]

    attrs = settings.Setting({})  # Maps data.name -> [attrs]

    def __init__(self):
        self.plots = []
        self.datas = OrderedDict()

        self.tree = tree = QTreeWidget(self,
                                       columnCount=1,
                                       allColumnsShowFocus=True,
                                       alternatingRowColors=True,
                                       selectionMode=QTreeWidget.ExtendedSelection,
                                       uniformRowHeights=True,
                                       headerHidden=True)
        tree.header().setStretchLastSection(True)
        # self.tree.itemSelectionChanged.connect(self.selectionChanged)

        vbox = gui.widgetBox(self.controlArea, box='Available features', orientation='vertical')
        vbox.layout().addWidget(tree)

        vbox = gui.widgetBox(self.mainArea, orientation='vertical')
        top = gui.widgetBox(vbox, orientation='horizontal')
        self.docks = DockArea()
        vbox.layout().addWidget(self.docks)
        overview = self.overview_plot = OverviewPlot(background='#fff')
        vbox.layout().addWidget(overview)



        top.layout().addStretch(1)
        gui.button(top, self, 'Add chart', callback=self.add_plot)
        # TODO: pyqtgraph.examples.CrossHair/MouseInteraction, ROI
        # TODO: PlotCustomization

    def add_plot(self):
        plot = pg.PlotWidget(background='#fff')
        dock = Dock('', plot)
        self.docks.addDock(dock)
        # TODO: pyqtgraph.ex.DockWidgets
        plot.addLegend(offset=(-30, 30))
        plot.showGrid(x=True, y=True)
        if self.plots:
            plot.setXLink(self.plots[-1])
        self.plots.append(plot)

    def populate_treeview(self):
        tree = self.tree
        tree.reset()
        BOLD_FONT = QFont('', -1, QFont.Bold)
        for data in self.datas.values():
            parent = QTreeWidgetItem([data.name or '<{}>'.format(data.__class__.__name__)])
            parent.setFont(0, BOLD_FONT)
            tree.addTopLevelItem(parent)
            for attr in data.domain:
                if not attr.is_continuous: continue
                item = QTreeWidgetItem(parent, [attr.name])
                item.setData(0, Qt.UserRole, attr)
        tree.expandAll()

    def set_data(self, data, id):
        if data is None:
            self._clear_data(id)
            self.datas.pop(id)
            return
        self.datas[id] = data
        self.populate_treeview()

        # self.plot.clear()
        # self.clear_legend()
        # if data is None:
        #     return
        # self.all_attrs = [(var.name, gui.attributeIconDict[var])
        #                   for var in data.domain
        #                   if (var is not data.time_variable and
        #                       isinstance(var, ContinuousVariable))]
        # self.attrs = [0]
        # self.on_changed()

    def clear_legend(self):
        """Why the fuck must I do this???"""
        for sample, label in list(self.plot.plotItem.legend.items):
            self.plot.plotItem.legend.removeItem(label.text)

    def on_changed(self):
        self.plot.clear()
        self.clear_legend()
        if not self.attrs:
            return

        periodograms = []
        max_i = -1  # The maximum freq to which pgrams should be plotted

        for attr, color in zip(self.attrs,
                               ColorPaletteGenerator(len(self.all_attrs))[self.attrs]):
            attr_idx = self.data.domain.index(self.all_attrs[attr][0])
            pgram = self.periodogram(attr_idx)
            periodograms.append((pgram, dict(pen=pg.mkPen(color, width=2),
                                             name=self.all_attrs[attr][0])))
            # Truncate plot values where the line is straight 0
            max_i = max(max_i, (pgram > .005).nonzero()[0][-1] + 50)
        for pgram, kwargs in periodograms:
            self.plot.plot(pgram[:max_i], **kwargs)
        self.plot.setRange(xRange=(0, max_i), yRange=(0, 1))
        self.plot.setLimits(xMin=-1.1, xMax=max_i, yMin=-.01, yMax=1.05)


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication

    a = QApplication([])
    ow = OWLineChart()

    data = Timeseries.dataset['yahoo_MSFT']
    # data = Timeseries.dataset['UCI-SML2010-1']
    ow.set_data(data, 0)

    ow.show()
    a.exec()
