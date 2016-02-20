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
from PyQt4.QtGui import QTreeWidget, QTreeWidgetItem, QFont, QSizePolicy, \
    QWidget, QPushButton, QStyle, QIcon, QHBoxLayout, QTreeView
from PyQt4.QtCore import Qt, QSize, pyqtSignal

from orangecontrib.timeseries.widgets.util import PlotWidget
from orangecontrib.timeseries import (
    Timeseries,
)

class OverviewPlot(pg.PlotWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

    def sizeHint(self):
        return QSize(2**23, 150)


@lru_cache(3)
def icon(key):
    from os.path import join, dirname
    return QIcon(join(dirname(__file__), 'icons', 'LineChart-{}.png'.format(key)))


_BUTTON_WIDTH = 30


class SinglePlot(QWidget):

    sig_closed = pyqtSignal(QWidget)

    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent

        self.tree = tree = QTreeView(self,
                                     alternatingRowColors=True,
                                     selectionMode=QTreeWidget.ExtendedSelection,
                                     uniformRowHeights=True,
                                     headerHidden=True,
                                     indentation=10,
                                     size=QSize(100, 100),
                                     sizePolicy=QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding))
        tree.setModel(parent.tree.model())
        tree.header().setStretchLastSection(True)
        tree.hide()

        selection = tree.selectionModel()
        selection.selectionChanged.connect(self.selection_changed)

        self.plot = plot = PlotWidget()
        plot.addLegend(offset=(-30, 30))
        plot.showGrid(x=True, y=True)

        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(0, 0, 0, 0)
        self.setLayout(hbox)
        hbox.addWidget(tree)
        hbox.addWidget(plot)

        self.buttons = buttons = []
        self.button_conf = button = QPushButton(icon('list'), '', plot,
                                                checkable=True)
        button.clicked.connect(self.popup_config)
        button.setGeometry(10, 10, _BUTTON_WIDTH, _BUTTON_WIDTH)
        buttons.append(button)

        self.button_close = button = QPushButton(icon('close'), '', plot)
        button.setGeometry(100, 100, _BUTTON_WIDTH, _BUTTON_WIDTH)
        button.clicked.connect(lambda: self.sig_closed.emit(self))
        buttons.append(button)

        for button in buttons:
            button.setVisible(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Reposition Close button
        x = self.plot.geometry().width() - 10 - _BUTTON_WIDTH
        self.button_close.setGeometry(x, 10, _BUTTON_WIDTH, _BUTTON_WIDTH)

    def enterEvent(self, event):
        for button in self.buttons:
            button.setVisible(True)

    def leaveEvent(self, event):
        for button in self.buttons:
            button.setVisible(False)

    def popup_config(self):
        self.tree.expandAll()
        self.tree.setVisible(self.button_conf.isChecked())

    def selection_changed(self, selected, deselected):
        plot = self.plot
        plot.clear()
        plot.plotItem.legend.items = []
        for mi in self.tree.selectionModel().selectedIndexes():
            if mi.parent().isValid():
                attr = mi.data(Qt.UserRole)
                id = mi.parent().data(Qt.UserRole)
                data = self.parent.datas[id]
                values = data[:, attr].X.T[0]
                plot.plot(values,
                          pen=pg.mkPen('#ff0000', width=2),
                          name=attr.name, )



class OWLineChart(widget.OWWidget):
    name = 'Line chart'
    description = "Visualize time series' progression."
    icon = 'icons/LineChart.svg'
    priority = 90

    inputs = [("Time series", Timeseries, 'set_data', widget.Multiple)]

    attrs = settings.Setting({})  # Maps data.name -> [attrs]

    want_control_area = False

    def __init__(self):
        self.plots = []
        self.datas = OrderedDict()

        self.tree = tree = QTreeWidget(columnCount=1,
                                       alternatingRowColors=True,
                                       selectionMode=QTreeWidget.ExtendedSelection,
                                       uniformRowHeights=True,
                                       headerHidden=True)

        vbox = gui.widgetBox(self.mainArea, orientation='vertical')
        top = gui.widgetBox(vbox, orientation='horizontal',
                            sizePolicy=QSizePolicy(
                                QSizePolicy.Expanding,
                                QSizePolicy.Minimum))
        top.layout().addStretch(1)
        button = QPushButton(icon('plus'), ' &Add plot', self,
                             size=QSize(_BUTTON_WIDTH, _BUTTON_WIDTH))
        button.clicked.connect(self.add_plot)
        top.layout().addWidget(button)

        self.plotsbox = gui.widgetBox(vbox, orientation='vertical',
                                      sizePolicy=QSizePolicy(
                                          QSizePolicy.Expanding,
                                          QSizePolicy.Expanding))
        overview = self.overview_plot = OverviewPlot(background='#fff')
        vbox.layout().addWidget(overview)

        self.add_plot()
        # TODO: pyqtgraph.examples.CrossHair/MouseInteraction, ROI
        # TODO: PlotCustomization

    def add_plot(self):
        plot = SinglePlot(self)
        if self.plots:
            plot.plot.setXLink(self.plots[-1].plot)
        self.plots.append(plot)
        plot.sig_closed.connect(self.close_plot)
        self.plotsbox.layout().addWidget(plot)

    def close_plot(self, widget):
        i = self.plots.index(widget)
        self.plots.pop(i)
        if i < len(self.plots):
            self.plots[i].plot.setXLink(self.plots[i - 1].plot if i > 0 else None)
        self.plotsbox.layout().removeWidget(widget)
        widget.setParent(None)

    def set_data(self, data, id):

        def tree_remove(id):
            row = list(self.datas.keys()).index(id)
            self.tree.takeTopLevelItem(row)

        def tree_add(id, data):
            top = QTreeWidgetItem(
                [data.name or '<{}>'.format(data.__class__.__name__)])
            top.setData(0, Qt.UserRole, id)
            top.setFont(0, QFont('', -1, QFont.Bold))
            self.tree.addTopLevelItem(top)
            for attr in data.domain.variables:
                if not attr.is_continuous or attr == data.time_variable:
                    continue
                item = QTreeWidgetItem(top, [attr.name])
                item.setData(0, Qt.UserRole, attr)
            self.tree.expandItem(top)

        if data is None:
            tree_remove(id)
            self.datas.pop(id)
        else:
            if id in self.datas:
                tree_remove(id)
            self.datas[id] = data
            tree_add(id, data)


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

    data = Timeseries('yahoo_MSFT')
    ow.set_data(data, 0)
    data = Timeseries('UCI-SML2010-1')
    ow.set_data(data, 1)
    ow.set_data(None, 1)

    ow.show()
    a.exec()
