from functools import lru_cache

from Orange.data import ContinuousVariable
from Orange.util import scale
from Orange.widgets import widget, gui, settings

import numpy as np
from PyQt4.QtGui import QListWidget

from orangecontrib.timeseries.util import cache_clears
from orangecontrib.timeseries import (
    Timeseries, periodogram as periodogram_equispaced, periodogram_nonequispaced
)
from Orange.widgets.highcharts import Highchart


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
        plot = self.plot = Highchart(
            self,
            enable_zoom=True,
            chart_type='column',
            plotOptions_line_marker_enabled=False,
            yAxis_min=0,
            yAxis_max=1.05,
            yAxis_showLastLabel=True,
            yAxis_endOnTick=False,
            xAxis_min=0,
            xAxis_gridLineWidth=1,
            yAxis_title_text='',
            xAxis_title_text='period',
            tooltip_headerFormat='period: {point.key:.2f}<br/>',
            tooltip_pointFormat='<span style="color:{point.color}">\u25CF</span> {point.y:.2f}<br/>',
        )
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
        if data is None:
            return
        self.all_attrs = [(var.name, gui.attributeIconDict[var])
                          for var in data.domain
                          if (var is not data.time_variable and
                              isinstance(var, ContinuousVariable))]
        self.attrs = [0]
        self.on_changed()

    def on_changed(self):
        if not self.attrs:
            return

        options = dict(series=[])
        max_x = 1  # The maximum period to which pgrams should be plotted
        for attr in self.attrs:
            attr_name = self.all_attrs[attr][0]
            attr_idx = self.data.domain.index(attr_name)
            periods, pgram = self.periodogram(attr_idx)
            # Truncate plot values where the line is straight 0
            i = max(0, (pgram > .05).nonzero()[0][0] - 20)
            max_x = max(max_x, periods[i])

            options['series'].append(dict(
                data=np.column_stack((periods, pgram))[::-1],
                name=attr_name))

        self.plot.chart(options, xAxis_max=max_x)


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    from PyQt4.QtCore import QTimer

    a = QApplication([])
    ow = OWPeriodogram()

    # data = Timeseries('yahoo_MSFT')
    data = Timeseries('UCI-SML2010-1')
    QTimer.singleShot(100, lambda: ow.set_data(data))

    ow.show()
    a.exec_()
