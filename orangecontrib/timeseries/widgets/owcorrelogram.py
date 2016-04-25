from functools import lru_cache

from Orange.data import ContinuousVariable
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.colorpalette import ColorPaletteGenerator
from orangecontrib.timeseries import (
    Timeseries, autocorrelation, partial_autocorrelation)
from orangecontrib.timeseries.util import cache_clears
from Orange.widgets.highcharts import Highchart


from PyQt4.QtGui import QListWidget


class OWCorrelogram(widget.OWWidget):
    name = 'Correlogram'
    description = "Visualize variables' auto-correlation."
    icon = 'icons/Correlogram.svg'
    priority = 110

    inputs = [("Time series", Timeseries, 'set_data')]

    attrs = settings.Setting([])
    use_pacf = settings.Setting(False)
    use_confint = settings.Setting(True)

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
            enable_zoom=True,
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
        if data is None:
            return
        self.all_attrs = [(var.name, gui.attributeIconDict[var])
                          for var in data.domain
                          if (var is not data.time_variable and
                              isinstance(var, ContinuousVariable))]
        self.attrs = [0]

    def on_changed(self):
        if not self.attrs:
            return

        series = []
        options = dict(series=series)
        for attr, color in zip(self.attrs,
                               ColorPaletteGenerator(len(self.all_attrs))[self.attrs]):
            attr_name = self.all_attrs[attr][0]
            attr_idx = self.data.domain.index(attr_name)
            pac = self.acf(attr_idx, self.use_pacf, self.use_confint)
            pac, confint = pac if self.use_confint else (pac, None)

            series.append(dict(
                data=pac,
                name=attr_name,
                lineWidth=2,
                zIndex=2,
            ))
            if confint is not None:
                series.append(dict(
                    type='arearange',
                    name='95% confidence',
                    data=confint,
                    enableMouseTracking=False,
                    linkedTo=':previous',
                    color='/**/ Highcharts.getOptions().colors[{}] /**/'.format(len(series) // 2),
                    lineWidth=0,
                    fillOpacity=.2,
                    zIndex=1,
                ))

        self.plot.chart(options, xAxis_type='linear')



if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    from PyQt4.QtCore import QTimer

    a = QApplication([])
    ow = OWCorrelogram()

    # data = Timeseries('yahoo_MSFT')
    data = Timeseries('UCI-SML2010-1')
    QTimer.singleShot(100, lambda: ow.set_data(data))

    ow.show()
    a.exec()
