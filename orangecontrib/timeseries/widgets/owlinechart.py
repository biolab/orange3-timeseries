from numbers import Number
from collections import OrderedDict
from os.path import join, dirname

import numpy as np

from Orange.data import TimeVariable, Table
from Orange.widgets import widget, gui, settings
from Orange.widgets.highcharts import Highchart

from PyQt4.QtGui import QTreeWidget, QSizePolicy, \
    QWidget, QPushButton, QIcon, QListView, QVBoxLayout
from PyQt4.QtCore import Qt, QSize, pyqtSignal, QTimer

from Orange.widgets.utils.itemmodels import VariableListModel
from orangecontrib.timeseries import Timeseries


class PlotConfigWidget(QWidget, gui.OWComponent):
    sigClosed = pyqtSignal(str, QWidget)
    sigLogarithmic = pyqtSignal(str, bool)
    sigType = pyqtSignal(str, str)
    sigSelection = pyqtSignal(str, list)

    is_logarithmic = False
    plot_type = 'line'

    def __init__(self, owwidget, ax, varmodel):
        QWidget.__init__(self, owwidget)
        gui.OWComponent.__init__(self)

        self.ax = ax
        self.view = view = QListView(self, selectionMode=QTreeWidget.ExtendedSelection,)
        view.setModel(varmodel)
        selection = view.selectionModel()
        selection.selectionChanged.connect(self.selection_changed)

        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        self.setLayout(box)

        hbox = gui.hBox(self)
        gui.comboBox(hbox, self, 'plot_type',
                     label='Type:',
                     orientation='horizontal',
                     items=('line', 'step line', 'column', 'area', 'spline'),
                     sendSelectedValue=True,
                     callback=lambda: self.sigType.emit(ax, self.plot_type))
        gui.rubber(hbox)
        self.button_close = button = QPushButton('×', hbox,
                                                 visible=False,
                                                 minimumSize=QSize(20, 20),
                                                 maximumSize=QSize(20, 20),
                                                 styleSheet='''
                                                     QPushButton {
                                                         font-weight: bold;
                                                         font-size:14pt;
                                                         margin:0;
                                                         padding:0;
                                                     }''')
        button.clicked.connect(lambda: self.sigClosed.emit(ax, self))
        hbox.layout().addWidget(button)
        gui.checkBox(self, self, 'is_logarithmic', 'Logarithmic axis',
                     callback=lambda: self.sigLogarithmic.emit(ax, self.is_logarithmic))
        box.addWidget(view)

    # This is here because sometimes enterEvent/leaveEvent below were called
    # before the constructor set button_close appropriately. I have no idea.
    button_close = None

    def enterEvent(self, event):
        if self.button_close:
            self.button_close.setVisible(True)

    def leaveEvent(self, event):
        if self.button_close:
            self.button_close.setVisible(False)

    def selection_changed(self):
        selection = [mi.model()[mi.row()]
                     for mi in self.view.selectionModel().selectedIndexes()]
        self.sigSelection.emit(self.ax, selection)


class Highstock(Highchart):

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args,
                         yAxis_lineWidth=2,
                         yAxis_labels_x=6,
                         yAxis_labels_y=-3,
                         yAxis_labels_align_x='right',
                         yAxis_title_text=None,
                         plotOptions_series_dataGrouping_groupPixelWidth=7,
                         plotOptions_areasplinerange_states_hover_lineWidthPlus=0,
                         plotOptions_areasplinerange_tooltip_pointFormat='''
                            <span style="color:{point.color}">\u25CF</span>
                            {series.name}: <b>{point.low:.2f} – {point.high:.2f}</b><br/>''',
                         **kwargs)
        self.parent = parent
        self.axes = []

    def _resizeAxes(self):
        if not self.axes:
            return
        MARGIN = 2
        HEIGHT = (100 - (len(self.axes) - 1) * MARGIN) // len(self.axes)
        self.evalJS('''
            var SKIP_AXES = 2,
                HEIGHT = %(HEIGHT)f,
                MARGIN = %(MARGIN)f;
            for (var i = 0; i < chart.yAxis.length - SKIP_AXES; ++i) {
                var top_offset = i * (HEIGHT + MARGIN);
                chart.yAxis[i + SKIP_AXES].update({
                    top: top_offset + '%%',
                    height: HEIGHT + '%%',
                    offset: 0  // Fixes https://github.com/highcharts/highcharts/issues/5199
                }, false);
            }
            chart.reflow();
            chart.redraw(false);
        ''' % locals())

    def addAxis(self):
        from random import random
        ax = 'ax_' + str(random())[2:]
        self.axes.append(ax)
        self.evalJS('''
            chart.addAxis({
                id: '%(ax)s',
            }, false, false, false);
        ''' % locals())
        self._resizeAxes()
        # TODO: multiple series on the bottom navigator, http://jsfiddle.net/highcharts/SD4XN/
        return ax

    def removeAxis(self, ax):
        self.axes.remove(ax)
        self.evalJS('''
            chart.get('%(ax)s').remove();
        ''' % dict(ax=ax))
        self._resizeAxes()

    def setXAxisType(self, ax_type):
        self.evalJS('''
        for (var i=0; i<chart.xAxis.length; ++i) {
            chart.xAxis[i].update({type: '%s'});
        }
        ''' % ax_type)

    def setSeries(self, ax, series):
        """TODO: Clean this shit up"""
        newseries = []
        names = []
        deltas = []
        forecasts = []
        forecasts_ci = []
        ci_percents = []

        data = self.parent.data
        delta = data.time_delta if isinstance(data.time_variable, TimeVariable) else None

        for attr in series:
            newseries.append(np.ravel(data[:, attr]))
            names.append(attr.name)
            deltas.append(None)
            forecasts.append(None)
            forecasts_ci.append(None)
            ci_percents.append(None)

            for forecast in self.parent.forecasts.values():
                fc_attr = attr.name + ' (forecast)'
                if fc_attr in forecast.domain:
                    fc_attr = forecast.domain[fc_attr]
                    # Forecast extends from last known value
                    forecasts[-1] = np.concatenate((newseries[-1][-1:],
                                                    np.ravel(forecast[:, fc_attr])))
                    # ci_attrs = forecast.attributes.get('ci_attrs', {})
                    # ci_low, ci_high = ci_attrs.get(fc_attr, (None, None))
                    ci_low, ci_high = getattr(fc_attr, 'ci_attrs', (None, None))
                    if ci_low in forecast.domain and ci_high in forecast.domain:
                        ci_percents[-1] = ci_low.ci_percent
                        forecasts_ci[-1] = np.row_stack((
                            [newseries[-1][-1]] * 2,  # last known value
                            np.column_stack((
                                np.ravel(forecast[:, ci_low]),
                                np.ravel(forecast[:, ci_high])))))
                    break

            if isinstance(data.time_variable, TimeVariable):
                delta = data.time_delta
                tvals = data.time_values

                if isinstance(delta, Number):
                    deltas[-1] = (tvals[0] * 1000, tvals[-1] * 1000, delta, None)
                elif delta:
                    deltas[-1] = (tvals[0] * 1000, tvals[-1] * 1000) + delta
                else:
                    newseries[-1] = np.column_stack((tvals * 1000,
                                                     newseries[-1]))
                    if forecasts[-1] is not None:
                        if forecast.time_variable:  # Use forecast time if available
                            fc_tvals = np.concatenate((tvals[-1:],
                                                       forecast.time_values * 1000))
                            forecasts[-1] = np.column_stack((
                                fc_tvals, forecasts[-1]))
                            forecasts_ci[-1] = np.column_stack((
                                fc_tvals, forecasts_ci[-1]))
                        else:  # Extrapolate from the final time of data
                            fc_tvals = np.linspace(
                                1000 * tvals[-1],
                                1000 * (tvals[-1] + (len(forecasts[-1]) - 1) * np.diff(tvals[-2:])[0]),
                                len(forecasts[-1]))
                            forecasts[-1] = np.column_stack((
                                fc_tvals, forecasts[-1]))
                            forecasts_ci[-1] = np.column_stack((
                                fc_tvals, forecasts_ci[-1]))

        self.exposeObject('series_' + ax, {'data': newseries,
                                           'forecasts': forecasts,
                                           'forecasts_ci': forecasts_ci,
                                           'ci_percents': ci_percents,
                                           'names': names,
                                           'deltas': deltas})
        self.evalJS('''
            var ax = chart.get('%(ax)s');
            chart.series
            .filter(function(s) { return s.yAxis == ax })
            .map(function(s) { s.remove(false); });

            var data = series_%(ax)s.data,
                names = series_%(ax)s.names,
                deltas = series_%(ax)s.deltas,
                forecasts = series_%(ax)s.forecasts,
                ci_percents = series_%(ax)s.ci_percents,
                forecasts_ci = series_%(ax)s.forecasts_ci;

            for (var i=0; i < data.length; ++i) {
                var opts = {
                    data: data[i],
                    name: names[i],
                    yAxis: '%(ax)s'
                };

                if (deltas[i]) {
                    opts.pointStart = deltas[i][0];
                    // skip 1: pointEnd (forecast start)
                    opts.pointInterval = deltas[i][2];
                    if (deltas[i][3])
                        opts.pointIntervalUnit = deltas[i][3];
                }

                var added_series = chart.addSeries(opts, false, false);

                if (forecasts[i]) {
                    var opts = {
                        linkedTo: ':previous',
                        name: names[i] + ' (forecast)',
                        yAxis: '%(ax)s',
                        data: forecasts[i],
                        dashStyle: 'ShortDash',
                        color: added_series.color,
                        fillOpacity: .3,
                    };
                    if (deltas[i]) {
                        opts.pointStart = deltas[i][1];
                        opts.pointInterval = deltas[i][2];
                        if (deltas[i][3])
                            opts.pointIntervalUnit = deltas[i][3];
                    }
                    chart.addSeries(opts, false, false)
                }
                if (forecasts_ci[i]) {
                    var opts = {
                        type: 'areasplinerange',
                        linkedTo: ':previous',
                        name: names[i] + ' (forecast; ' + ci_percents[i] + '%% CI)',
                        yAxis: '%(ax)s',
                        data: forecasts_ci[i],
                        color: added_series.color,
                        fillOpacity: 0.2,
                        lineWidth: 0,
                    };
                    if (deltas[i]) {
                        opts.pointStart = deltas[i][1];
                        opts.pointInterval = deltas[i][2];
                        if (deltas[i][3])
                            opts.pointIntervalUnit = deltas[i][3];
                    }
                    chart.addSeries(opts, false, false)
                }
            }
            chart.redraw(false);
        ''' % dict(ax=ax))

    def setLogarithmic(self, ax, is_logarithmic):
        self.evalJS('''
            chart.get('%(ax)s').update({ type: '%(type)s' });
        ''' % dict(ax=ax, type='logarithmic' if is_logarithmic else 'linear'))

    def setType(self, ax, type):
        step, type = ('true', 'line') if type == 'step line' else ('false', type)
        self.evalJS('''
            var ax = chart.get('%(ax)s');
            chart.series
            .filter(function(s) { return s.yAxis == ax; })
            .map(function(s) {
                s.update({
                    type: '%(type)s',
                    step: %(step)s
                }, false);
            });
            chart.redraw(false);
        ''' % locals())

    def enable_rangeSelector(self, enable):
        display = 'initial' if enable else 'none'
        self.evalJS(
            '$(".highcharts-range-selector-buttons, '
            '   .highcharts-input-group").css({display: "%s"});' % display)
        # Reset the range selector to full view
        if not enable:
            self.evalJS('$(chart.rangeSelector.buttons[5]).click();')


class OWLineChart(widget.OWWidget):
    name = 'Line Chart'
    description = "Visualize time series' sequence and progression."
    icon = 'icons/LineChart.svg'
    priority = 90

    inputs = [("Time series", Table, 'set_data'),
              ('Forecast', Timeseries, 'set_forecast', widget.Multiple)]

    attrs = settings.Setting({})  # Maps data.name -> [attrs]

    def __init__(self):
        self.data = None
        self.plots = []
        self.configs = []
        self.forecasts = OrderedDict()
        self.varmodel = VariableListModel(parent=self)
        icon = QIcon(join(dirname(__file__), 'icons', 'LineChart-plus.png'))
        self.add_button = button = QPushButton(icon, ' &Add plot', self)
        button.clicked.connect(self.add_plot)
        self.controlArea.layout().addWidget(button)
        self.configsArea = gui.vBox(self.controlArea)
        self.controlArea.layout().addStretch(1)
        # TODO: allow selecting ranges that are sent to output as subset table
        self.chart = highstock = Highstock(self, highchart='StockChart')
        self.mainArea.layout().addWidget(highstock)
        highstock.chart()
        QTimer.singleShot(0, self.add_plot)

    def add_plot(self):
        ax = self.chart.addAxis()
        config = PlotConfigWidget(self, ax, self.varmodel)
        # Connect the signals
        config.sigSelection.connect(self.chart.setSeries)
        config.sigLogarithmic.connect(self.chart.setLogarithmic)
        config.sigType.connect(self.chart.setType)
        config.sigClosed.connect(self.chart.removeAxis)
        config.sigClosed.connect(lambda ax, widget: widget.setParent(None))
        config.sigClosed.connect(lambda ax, widget:
                                 self.add_button.setDisabled(False))
        self.configs.append(config)
        self.add_button.setDisabled(len(self.configs) >= 5)
        self.configsArea.layout().addWidget(config)

    def set_data(self, data):
        # TODO: set xAxis resolution and tooltip time contents depending on
        # data.time_delta. See: http://imgur.com/yrnlgQz

        # If the same data is updated, short circuit to just updating the chart,
        # retaining all panels and list view selections ...
        if data is not None and self.data is not None and data.domain == self.data.domain:
            self.data = Timeseries.from_data_table(data)
            for config in self.configs:
                config.selection_changed()
            return

        self.data = data = None if data is None else Timeseries.from_data_table(data)
        if data is None:
            self.chart.clear()
            return
        if getattr(data.time_variable, 'utc_offset', False):
            offset_minutes = data.time_variable.utc_offset.total_seconds() / 60
            self.chart.evalJS('Highcharts.setOptions({global: {timezoneOffset: %d}});' % -offset_minutes)  # Why is this negative? It works.
            self.chart.chart()

        self.chart.setXAxisType(
            'datetime'
            if (data.time_variable and
                (getattr(data.time_variable, 'have_date', False) or
                 getattr(data.time_variable, 'have_time', False))) else
            'linear')

        self.varmodel.wrap([var for var in data.domain
                            if var.is_continuous and var != data.time_variable])
        self.chart.enable_rangeSelector(
            isinstance(data.time_variable, TimeVariable))

    def set_forecast(self, forecast, id):
        if forecast is not None:
            self.forecasts[id] = forecast
        else:
            self.forecasts.pop(id, None)
        # TODO: update currently shown plots


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    from orangecontrib.timeseries import ARIMA, VAR

    a = QApplication([])
    ow = OWLineChart()

    msft = Timeseries('yahoo_MSFT')
    ow.set_data(msft),
    # ow.set_data(Timeseries('UCI-SML2010-1'))

    msft = msft.interp()
    model = ARIMA((3, 1, 1)).fit(msft)
    ow.set_forecast(model.predict(10, as_table=True), 0)
    model = VAR(4).fit(msft)
    ow.set_forecast(model.predict(10, as_table=True), 1)

    ow.show()
    a.exec()
