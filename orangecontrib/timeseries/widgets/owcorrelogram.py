import numpy as np

from AnyQt.QtCore import Qt
import pyqtgraph as pg

from orangecontrib.timeseries.widgets.owperiodbase import OWPeriodBase
from orangewidget.settings import Setting
from orangewidget.utils.widgetpreview import WidgetPreview

from Orange.widgets import gui

from orangecontrib.timeseries import (
    Timeseries, autocorrelation, partial_autocorrelation)


class OWCorrelogram(OWPeriodBase):
    # TODO: allow computing cross-correlation of two distinct series
    name = 'Correlogram'
    description = "Visualize variables' auto-correlation."
    icon = 'icons/Correlogram.svg'
    priority = 110

    use_pacf = Setting(False)
    use_confint = Setting(True)

    yrange = (-1, 1)

    def __init__(self):
        super().__init__()
        gui.separator(self.controlArea)
        gui.checkBox(self.controlArea, self, 'use_pacf',
                     label='Compute partial auto-correlation',
                     callback=self.replot)
        gui.checkBox(self.controlArea, self, 'use_confint',
                     label='Plot 95% significance interval',
                     callback=self.replot)

    def acf(self, attr, pacf, confint):
        key = (attr, pacf, confint)
        if key not in self._cached:
            x = self.data.interp(attr).ravel()
            func = partial_autocorrelation if pacf else autocorrelation
            self._cached[key] = func(x, alpha=.05 if confint else None)
        return self._cached[key]

    def replot(self):
        self.plot.clear()
        if not self.selection:
            return

        self.plot_widget.addItem(pg.InfiniteLine(0, 0, pen=pg.mkPen(0., width=2)))

        palette = self.get_palette()
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
