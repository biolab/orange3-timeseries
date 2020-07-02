from functools import lru_cache

from Orange.data import Table, ContinuousVariable
from Orange.widgets import widget, gui, settings
from Orange.widgets.widget import Input

import numpy as np
from AnyQt.QtWidgets import QListWidget

from orangecontrib.timeseries.util import cache_clears
from orangecontrib.timeseries import (
    Timeseries, periodogram as periodogram_equispaced, periodogram_nonequispaced
)
from orangecontrib.timeseries.widgets.highcharts import Highchart


class OWPeriodogram(widget.OWWidget):
    name = 'Periodogram'
    description = "Visualize time series' cycles, seasonality, periodicity, " \
                  "and most significant frequencies."
    icon = 'icons/Periodogram.svg'
    priority = 100

    class Inputs:
        time_series = Input("Time series", Table)

    attrs = settings.Setting([])

    graph_name = 'plot'

    def __init__(self):
        self.all_attrs = []
        gui.listBox(self.controlArea, self, 'attrs',
                    labels='all_attrs',
                    box='Periodogram attribute(s)',
                    selectionMode=QListWidget.ExtendedSelection,
                    callback=self.on_changed)
        plot = self.plot = Highchart(
            self,
            # enable_zoom=True,
            chart_zoomType='x',
            chart_type='column',
            plotOptions_column_borderWidth=0,
            plotOptions_column_groupPadding=0,
            plotOptions_series_pointWidth=3,
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
        # TODO: non-equispaced periodogram should let the user set minimal and maximal frequencies to test

    @lru_cache(20)
    def periodogram(self, attr):
        if self.data.time_delta.is_equispaced:
            x = np.ravel(self.data.interp(attr))
            periods, pgram = periodogram_equispaced(x)
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

            periods, pgram = periodogram_nonequispaced(times, x)
        return periods, pgram

    @cache_clears(periodogram)
    @Inputs.time_series
    def set_data(self, data):
        self.data = data = None if data is None else \
                           Timeseries.from_data_table(data)
        self.all_attrs = []
        if data is None:
            self.plot.clear()
            return
        self.all_attrs = [(var.name, gui.attributeIconDict[var])
                          for var in data.domain.variables
                          if (var is not data.time_variable and
                              isinstance(var, ContinuousVariable))]
        self.attrs = [0]
        self.on_changed()

    def on_changed(self):
        if not self.attrs or not self.all_attrs:
            return

        options = dict(series=[])
        for attr in self.attrs:
            attr_name = self.all_attrs[attr][0]
            periods, pgram = self.periodogram(attr_name)

            options['series'].append(dict(
                data=np.column_stack((periods, pgram)),
                name=attr_name))

        self.plot.chart(options)


if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication

    a = QApplication([])
    ow = OWPeriodogram()

    data = Timeseries.from_file('airpassengers')
    ow.set_data(data)

    ow.show()
    a.exec_()
