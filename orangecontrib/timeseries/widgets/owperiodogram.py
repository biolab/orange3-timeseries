from PyQt4.QtCore import Qt
from functools import lru_cache

from Orange.data import ContinuousVariable
from Orange.util import scale
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.colorpalette import ColorPaletteGenerator

import pyqtgraph as pg
from PyQt4.QtGui import QListWidget, QFont

from orangecontrib.timeseries.util import cache_clears
from orangecontrib.timeseries import (
    Timeseries, periodogram as periodogram_equispaced, periodogram_nonequispaced
)


class PlotWidget(pg.PlotWidget):

    class ViewBox(pg.ViewBox):
        """From pg.examples.PlotCustomization"""
        def __init__(self, *args, **kwds):
            super().__init__(*args, **kwds)
            self.setMouseMode(self.RectMode)

        def mouseClickEvent(self, ev):
            if ev.button() == Qt.RightButton:
                self.autoRange()

    def __init__(self, **kwargs):
        """From pg.examples.Crosshair+MouseInteraction"""
        vb = self.ViewBox()
        super().__init__(background='#fff',
                         viewBox=vb,
                         enableMenu=False)

        label = pg.TextItem(color='#000')
        font = QFont("", 10.5, QFont.Bold)
        label.setFont(font)
        vLine = pg.InfiniteLine(angle=90, movable=False)
        vb.addItem(label)
        vb.addItem(vLine, ignoreBounds=True)

        def mouseMoved(evt):
            # pos = evt[0]  # SignalProxy turns original args into a tuple
            pos = evt
            if vb.sceneBoundingRect().contains(pos):
                pos = vb.mapSceneToView(pos)
                label.setText("  period=%0.1f" % pos.x())
                vLine.setPos(pos.x())
                label.setPos(pos)

        self.plotItem.scene().sigMouseMoved.connect(mouseMoved)
        # FIXME: For some reason, th line below, copied from example, doesn't work
        # pg.SignalProxy(self.plotItem.scene().sigMouseMoved,
        #                rateLimit=60, slot=mouseMoved)


class OWPeriodogram(widget.OWWidget):
    name = 'Periodogram'
    description = "Visualize time series' (non-)periodicity and most " \
                  "significant frequencies."
    icon = 'icons/Periodogram.svg'
    priority = 100

    inputs = [("Time series", Timeseries, 'set_data')]

    attrs = settings.Setting([])

    def __init__(self):
        self.all_attrs = []
        gui.listBox(self.controlArea, self, 'attrs',
                    labels='all_attrs',
                    box='Periodogram attribute(s)',
                    selectionMode=QListWidget.ExtendedSelection,
                    callback=self.on_changed)
        plot = self.plot = PlotWidget()
        plot.addLegend(offset=(-30, 30))
        plot.showGrid(x=True, y=True)
        plot.hideAxis('left')
        plot.setLabel('bottom', 'period', units='#steps')
        self.mainArea.layout().addWidget(plot)

    @lru_cache(20)
    def periodogram(self, attr):
        if attr < self.data.X.shape[1]:
            x = self.data.X[:, attr]
        else:
            if self.data.Y.ndim == 2:
                x = self.data.Y[:, attr - self.data.X.shape[1]]
            else:
                x = self.data.Y

        if self.data.is_equispaced:
            periods, pgram = periodogram_equispaced(x, detrend='constant')
        else:
            times = self.data.time_values
            periods, pgram = periodogram_nonequispaced(times, x, detrend='linear')
        return periods, scale(pgram)

    @cache_clears(periodogram)
    def set_data(self, data):
        self.data = data
        self.all_attrs = []
        self.plot.clear()
        self.clear_legend()
        if data is None:
            return
        self.all_attrs = [(var.name, gui.attributeIconDict[var])
                          for var in data.domain
                          if (var is not data.time_variable and
                              isinstance(var, ContinuousVariable))]
        self.attrs = [0]
        self.on_changed()

    def clear_legend(self):
        """Why the fuck must I do this???"""
        for sample, label in list(self.plot.plotItem.legend.items):
            self.plot.plotItem.legend.removeItem(label.text)

    def on_changed(self):
        self.plot.clear()
        self.clear_legend()
        if not self.attrs:
            return

        max_x = 1  # The maximum period to which pgrams should be plotted
        for attr, color in zip(self.attrs,
                               ColorPaletteGenerator(len(self.all_attrs))[self.attrs]):
            attr_idx = self.data.domain.index(self.all_attrs[attr][0])
            periods, pgram = self.periodogram(attr_idx)
            self.plot.plot(periods, pgram,
                           pen=pg.mkPen(color, width=2),
                           name=self.all_attrs[attr][0])
            # Truncate plot values where the line is straight 0
            i = max(0, (pgram > .05).nonzero()[0][0] - 20)
            max_x = max(max_x, periods[i])

        self.plot.setRange(xRange=(0, max_x), yRange=(0, 1))
        self.plot.setLimits(xMin=-1.1, xMax=max_x, yMin=-.01, yMax=1.05)


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication

    a = QApplication([])
    ow = OWPeriodogram()

    # data = Timeseries.dataset['yahoo_MSFT']
    data = Timeseries.dataset['UCI-SML2010-1']
    ow.set_data(data)

    ow.show()
    a.exec()
