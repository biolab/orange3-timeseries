from functools import lru_cache

from Orange.data import ContinuousVariable
from Orange.util import scale
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.colorpalette import ColorPaletteGenerator

import pyqtgraph as pg
from PyQt4.QtGui import QListWidget

from orangecontrib.timeseries.util import cache_clears
from orangecontrib.timeseries import (
    Timeseries, periodogram as periodogram_equispaced, periodogram_nonequispaced
)


class OWPeriodogram(widget.OWWidget):
    name = 'Periodogram'
    description = "Visualize time series' (non-)periodicity."
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
        plot = self.plot = pg.PlotWidget(background='#fff')
        plot.addLegend(offset=(-30, 30))
        self.plot.showGrid(x=True, y=True)
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
            pgram = periodogram_equispaced(x)
        else:
            times = self.data.time_values
            pgram = periodogram_nonequispaced(times, x)
        return scale(pgram)

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
    ow = OWPeriodogram()

    # data = Timeseries.dataset['yahoo_MSFT']
    data = Timeseries.dataset['UCI-SML2010-1']
    ow.set_data(data)

    ow.show()
    a.exec()
