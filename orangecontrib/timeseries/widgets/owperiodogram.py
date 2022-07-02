import numpy as np
import pyqtgraph as pg

from orangewidget.utils.widgetpreview import WidgetPreview

from orangecontrib.timeseries import \
    Timeseries, periodogram as periodogram_equispaced, periodogram_nonequispaced
from orangecontrib.timeseries.widgets.owperiodbase import OWPeriodBase


class OWPeriodogram(OWPeriodBase):
    name = 'Periodogram'
    description = "Visualize time series' cycles, seasonality, periodicity, " \
                  "and most significant frequencies."
    icon = 'icons/Periodogram.svg'
    priority = 100

    yrange = (0, 1)

    def periodogram(self, attr):
        if attr not in self._cached:
            if getattr(self.data.time_delta, "is_equispaced", True):
                x = np.ravel(self.data.interp(attr))
                self._cached[attr] = periodogram_equispaced(x)
                # TODO: convert periods into time_values-relative values, i.e.
                # periods *= self.data.time_delta; like lombscargle already does
                # periods *= self.data.time_delta
            else:
                times = np.asanyarray(self.data.time_values, dtype=float)
                x = np.ravel(self.data[:, attr])
                # Since lombscargle works with explicit times,
                # we can skip any nan values
                nonnan = ~np.isnan(x)
                if not nonnan.all():
                    x, times = x[nonnan], times[nonnan]
                self._cached[attr] = periodogram_nonequispaced(times, x)
        return self._cached[attr]

    def replot(self):
        self.plot.clear()
        if not self.selection:
            return

        palette = self.get_palette()
        for i, attr in enumerate(self.selection):
            color = palette.value_to_qcolor(i)
            periods, grams = self.periodogram(attr)
            x = np.repeat(periods, 2)
            y = np.vstack((np.zeros(len(grams)), grams)).T.flatten()
            item = pg.PlotCurveItem(
                x=x, y=y, connect="pairs", antialias=True,
                pen=pg.mkPen(color, width=5))
            self.plot_widget.addItem(item)


if __name__ == "__main__":
    WidgetPreview(OWPeriodogram).run(
        Timeseries.from_url("http://datasets.biolab.si/core/slovenia-traffic-accidents-2016-events.tab")
    )

