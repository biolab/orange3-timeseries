from functools import lru_cache

from Orange.data import Table, ContinuousVariable
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.colorpalette import ColorPaletteGenerator
from orangecontrib.timeseries import (
    Timeseries, autocorrelation, partial_autocorrelation)
from orangecontrib.timeseries.util import cache_clears
from orangecontrib.timeseries.widgets.highcharts import Highchart

from AnyQt.QtWidgets import QListWidget
from AnyQt.QtCore import QTimer


class OWCorrelogram(widget.OWWidget):
    # TODO: allow computing cross-correlation of two distinct series
    name = 'Correlogram'
    description = "Visualize variables' auto-correlation."
    icon = 'icons/Correlogram.svg'
    priority = 110

    inputs = [("Time series", Table, 'set_data')]

    attrs = settings.Setting([])
    use_pacf = settings.Setting(False)
    use_confint = settings.Setting(True)

    graph_name = 'plot'

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
        plot = self.plot = Highchart(
            self,
            chart_zoomType='x',
            plotOptions_line_marker_enabled=False,
            plotOptions_column_borderWidth=0,
            plotOptions_column_groupPadding=0,
            plotOptions_series_pointWidth=3,
            yAxis_min=-1.0,
            yAxis_max=1.0,
            xAxis_min=0,
            xAxis_gridLineWidth=1,
            yAxis_plotLines=[dict(value=0, color='#000', width=1, zIndex=2)],
            yAxis_title_text='',
            xAxis_title_text='period',
            tooltip_headerFormat='Correlation at period: {point.key:.2f}<br/>',
            tooltip_pointFormat='<span style="color:{point.color}">\u25CF</span> {point.y:.2f}<br/>',
        )
        self.mainArea.layout().addWidget(plot)

    def acf(self, attr, pacf, confint):
        x = self.data.interp(attr).ravel()
        func = partial_autocorrelation if pacf else autocorrelation
        return func(x, alpha=.05 if confint else None)

    def set_data(self, data):
        self.data = data = None if data is None else Timeseries.from_data_table(data)
        self.all_attrs = []
        if data is None:
            self.plot.clear()
            return
        self.all_attrs = [(var.name, gui.attributeIconDict[var])
                          for var in data.domain
                          if (var is not data.time_variable and
                              isinstance(var, ContinuousVariable))]
        self.attrs = [0]
        self.on_changed()

    def on_changed(self):
        if not self.attrs or not self.all_attrs:
            return

        series = []
        options = dict(series=series)
        plotlines = []
        for i, (attr, color) in enumerate(zip(self.attrs,
                                              ColorPaletteGenerator(len(self.all_attrs))[self.attrs])):
            attr_name = self.all_attrs[attr][0]
            pac = self.acf(attr_name, self.use_pacf, False)

            if self.use_confint:
                # Confidence intervals, from:
                # https://www.mathworks.com/help/econ/autocorrelation-and-partial-autocorrelation.html
                # https://www.mathworks.com/help/signal/ug/confidence-intervals-for-sample-autocorrelation.html
                std = 1.96 * ((1 + 2 * (pac[:, 1]**2).sum()) / len(self.data))**.5  # = more precise than 1.96/sqrt(N)
                color = '/**/ Highcharts.getOptions().colors[{}] /**/'.format(i)
                line = dict(color=color, width=1.5, dashStyle='dash')
                plotlines.append(dict(line, value=std))
                plotlines.append(dict(line, value=-std))

            series.append(dict(
                # TODO: set units to something more readable than #periods (e.g. days)
                data=pac,
                type='column',
                name=attr_name,
                zIndex=2,
            ))

        # TODO: give periods meaning (datetime names)
        plotlines.append(dict(value=0, color='black', width=2, zIndex=3))
        if series:
            self.plot.chart(options, yAxis_plotLines=plotlines, xAxis_type='linear')
        else:
            self.plot.clear()


if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication

    a = QApplication([])
    ow = OWCorrelogram()

    # data = Timeseries('yahoo_MSFT')
    data = Timeseries('UCI-SML2010-1')
    ow.set_data(data)

    ow.show()
    a.exec()
