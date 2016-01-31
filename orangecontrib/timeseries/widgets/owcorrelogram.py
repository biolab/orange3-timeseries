from functools import lru_cache

from Orange.data import ContinuousVariable
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.colorpalette import ColorPaletteGenerator
from orangecontrib.timeseries import (
    Timeseries, autocorrelation, partial_autocorrelation)
from orangecontrib.timeseries.util import cache_clears
from orangecontrib.timeseries.widgets.owperiodogram import PlotWidget

import pyqtgraph as pg

from PyQt4.QtGui import QListWidget


class OWCorrelogram(widget.OWWidget):
    name = 'Correlogram'
    description = "Visualize variables' auto-correlation."
    icon = 'icons/Correlogram.svg'
    priority = 110

    inputs = [("Time series", Timeseries, 'set_data')]

    attrs = settings.Setting([])
    use_pacf = settings.Setting(False)
    use_confint = settings.Setting(False)

    def __init__(self):
        self.all_attrs = []
        opts = gui.widgetBox(self.controlArea, 'Options')
        gui.checkBox(opts, self, 'use_pacf',
                     label='Compute partial auto-correlation (PACF)',
                     callback=self.on_changed)
        gui.checkBox(opts, self, 'use_confint',
                     label='Plot 95% significance interval',
                     callback=self.on_changed)
        gui.listBox(self.controlArea, self, 'attrs',
                    labels='all_attrs',
                    box='Auto-correlated attribute(s)',
                    selectionMode=QListWidget.ExtendedSelection,
                    callback=self.on_changed)
        plot = self.plot = PlotWidget(background='#fff')
        plot.addLegend(offset=(-30, 30))
        self.plot.showGrid(x=True, y=True)
        self.mainArea.layout().addWidget(plot)

    @lru_cache(20)
    def acf(self, attr, pacf, confint):
        if attr < self.data.X.shape[1]:
            x = self.data.X[:, attr]
        else:
            if self.data.Y.ndim == 2:
                x = self.data.Y[:, attr - self.data.X.shape[1]]
            else:
                x = self.data.Y

        func = partial_autocorrelation if pacf else autocorrelation
        return func(x, alpha=.05 if confint else None)

    @cache_clears(acf)
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
        """He was fucking insane, whoever designed this!"""
        for sample, label in list(self.plot.plotItem.legend.items):
            self.plot.plotItem.legend.removeItem(label.text)

    def on_changed(self):
        self.plot.clear()
        self.clear_legend()
        if not self.attrs:
            return

        for attr, color in zip(self.attrs,
                               ColorPaletteGenerator(len(self.all_attrs))[self.attrs]):
            attr_idx = self.data.domain.index(self.all_attrs[attr][0])
            pac = self.acf(attr_idx, self.use_pacf, self.use_confint)
            pac, confint = pac if self.use_confint else (pac, None)
            self.plot.plot(pac,
                           pen=pg.mkPen(color.darker(180), width=2),
                           name=self.all_attrs[attr][0])
            if confint is not None:
                self.plot.plot(confint[:, 0], pen=pg.mkPen(color, width=1))
                self.plot.plot(confint[:, 1], pen=pg.mkPen(color, width=1))

        self.plot.setRange(xRange=(0, len(pac)), yRange=(-1, 1))
        self.plot.setLimits(xMin=-1.1, xMax=len(pac) + 50, yMin=-1.05, yMax=1.05)



if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    a = QApplication([])
    ow = OWCorrelogram()

    # data = Timeseries.dataset['yahoo_MSFT']
    data = Timeseries.dataset['UCI-SML2010-1']
    ow.set_data(data)

    ow.show()
    a.exec()
