from numbers import Number
from collections import OrderedDict
from os.path import join, dirname
from typing import List

import numpy as np
from AnyQt.QtWidgets import (
    QTreeWidget,
    QWidget,
    QPushButton,
    QListView,
    QVBoxLayout,
)
from AnyQt.QtGui import QIcon, QCloseEvent
from AnyQt.QtCore import QSize, pyqtSignal

from orangewidget.utils.widgetpreview import WidgetPreview
from Orange.data import TimeVariable, Table, Variable
from Orange.widgets import gui
from Orange.widgets.widget import OWWidget, Input, AttributeList
from Orange.widgets.utils import vartype
from Orange.widgets.settings import (
    ContextSetting,
    IncompatibleContext,
    DomainContextHandler,
)
from Orange.widgets.utils.itemmodels import VariableListModel

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.highcharts import Highchart


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
        self.view = view = QListView(
            self, selectionMode=QTreeWidget.ExtendedSelection,
        )
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
        gui.checkBox(
            self,
            self,
            "is_logarithmic",
            "Logarithmic axis",
            callback=self.on_logarithmic,
        )
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

    def on_logarithmic(self) -> None:
        """
        Callback when changes the the scale to logarithmic or back
        """
        self.sigLogarithmic.emit(self.ax, self.is_logarithmic)

    def selection_changed(self):
        selection = self.get_selection()
        self.sigSelection.emit(self.ax, selection)
        self.sigType.emit(self.ax, self.plot_type)

    def get_selection(self) -> List[Variable]:
        """
        Get variables selected in the view.

        Returns
        -------
        List with selected variables
        """
        return [
            mi.model()[mi.row()]
            for mi in self.view.selectionModel().selectedIndexes()
        ]

    def set_selection(self, values: List[Variable]) -> None:
        """
        Select variables in list and update the graph.

        Parameters
        ----------
        values
            Variables to select
        """
        sel_model = self.view.selectionModel()
        sel_model.clearSelection()
        model = self.view.model()
        for v in values:
            index = model.indexOf(v)
            index = model.index(index, 0)
            sel_model.select(index, sel_model.Select)

    def set_logarithmic(self, is_log: bool) -> None:
        """
        Set is logarithmic setting and update the graph.

        Parameters
        ----------
        is_log
            Boolean that indicates whether to set scale to logarithmic.
        """
        self.is_logarithmic = is_log
        self.on_logarithmic()


class Highstock(Highchart):

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args,
                         yAxis_lineWidth=2,
                         yAxis_labels_x=6,
                         yAxis_labels_y=-3,
                         yAxis_labels_align_x='right',
                         yAxis_title_text=None,
                         enable_scrollbar = False,
                         plotOptions_series_dataGrouping_groupPixelWidth=2,
                         plotOptions_series_dataGrouping_approximation='high',
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
            var SKIP_AXES = 1,
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

    def add_legend(self):
        self.evalJS('''chart.legend.options.enabled = true;''')

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

        for attr in series:
            newseries.append(data.get_column_view(attr)[0])
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
                delta = data.time_delta.backwards_compatible_delta
                tvals = data.time_values

                if isinstance(delta, Number):
                    deltas[-1] = (tvals[0] * 1000, tvals[-1] * 1000, delta * 1000, None)
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
            chart.get('%(ax)s').update({ type: '%(type)s', allowNegativeLog:
            %(negative)s, tickInterval: %(tick)s,
        });
        ''' % dict(ax=ax, type='logarithmic' if is_logarithmic else 'linear',
                   negative='true' if is_logarithmic else 'false',
                   tick=1 if is_logarithmic else 'undefined'))
        if not is_logarithmic:
            # it is a workaround for Highcharts issue - Highcharts do not
            # un-mark data as null when changing graph from logarithmic to
            # linear
            self.evalJS(
                '''
                s = chart.get('%(ax)s').series;
                s.forEach(function(series) {
                    series.data.forEach(function(point) {
                        point.update({'isNull': false});
                    });
                });
                ''' % dict(ax=ax)
            )

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


class LineChartContextHandler(DomainContextHandler):
    """
    Context handler of line chart. The specifics of this widget is
    that `attrs` variable is list of lists and it is not handled with
    the DomainContextHandler.
    """

    def encode_setting(self, context, setting, value):
        if setting.name == "attrs":
            value = [
                [(var.name, vartype(var)) for var in plot] for plot in value
            ]
        return super().encode_setting(context, setting, value)

    def decode_setting(self, setting, value, domain=None, *_args):
        decoded = super().decode_setting(setting, value, domain)
        if setting.name == "attrs":
            decoded = [[domain[name] for name, _ in plot] for plot in decoded]
        return decoded

    def match(self, context, _, attrs, metas):
        if context.attributes == attrs and context.metas == metas:
            return self.PERFECT_MATCH

        if "attrs" not in context.values:
            return self.NO_MATCH

        all_vars = attrs.copy()
        all_vars.update(metas)

        value = set(y for x in context.values["attrs"] for y in x)
        return sum(all_vars.get(attr) == vtype for attr, vtype in value) / len(
            value
        )


class OWLineChart(OWWidget):
    name = 'Line Chart'
    description = "Visualize time series' sequence and progression."
    icon = 'icons/LineChart.svg'
    priority = 90

    class Inputs:
        time_series = Input("Time series", Table)
        features = Input("Features", AttributeList)
        forecast = Input("Forecast", Timeseries, multiple=True)

    settingsHandler = LineChartContextHandler()
    attrs = ContextSetting([])  # Maps data.name -> [attrs]
    is_logit = ContextSetting([])

    graph_name = 'chart'

    def __init__(self):
        self.data = None
        self.features = None
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
        # highstock.evalJS('Highcharts.setOptions({navigator: {enabled:false}});')
        highstock.chart(
            # For some reason, these options don't work as global opts applied at Highstock init time
            # Disable top range selector
            rangeSelector_enabled=False,
            rangeSelector_inputEnabled=False,
            # Disable bottom miniview navigator (it doesn't update)
            navigator_enabled=False, )
        self.add_plot()
        self.chart.add_legend()

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
        config.sigClosed.connect(lambda ax, widget: self.remove_plot(widget))

        self.configsArea.layout().addWidget(config)

    def remove_plot(self, plot):
        self.configs.remove(plot)
        # # self.configsArea.layout()
        if len(self.chart.axes) < 2:
            self.resize(QSize(925, 635))

    @Inputs.time_series
    def set_data(self, data):
        # TODO: set xAxis resolution and tooltip time contents depending on
        # data.time_delta. See: http://imgur.com/yrnlgQz

        # If the same data is updated, short circuit to just updating the chart
        # retaining all panels and list view selections ...
        new_data = None if data is None else \
                   Timeseries.from_data_table(data)
        if new_data is not None and self.data is not None \
                and new_data.domain == self.data.domain:
            self.data = new_data
            self._selections_changed()
            return

        self.data = data = new_data
        if data is None:
            self.varmodel.clear()
            self.chart.clear()
            return

        self.set_attributes()

        if getattr(data.time_variable, 'utc_offset', False):
            offset_minutes = data.time_variable.utc_offset.total_seconds() / 60
            self.chart.evalJS(
                'Highcharts.setOptions({global: {timezoneOffset: %d}});'
                % -offset_minutes
            )  # Why is this negative? It works.
            self.chart.chart()

        self.chart.setXAxisType(
            'datetime'
            if (data.time_variable and
                (getattr(data.time_variable, 'have_date', False) or
                 getattr(data.time_variable, 'have_time', False))) else
            'linear')

        variables = [
            var
            for var in data.domain.variables
            if var.is_continuous and var != data.time_variable
        ]
        self.varmodel.wrap(variables)
        self.update_plots()

    @Inputs.forecast
    def set_forecast(self, forecast, id):
        if forecast is not None:
            self.forecasts[id] = forecast
        else:
            self.forecasts.pop(id, None)
        # TODO: update currently shown plots

    @Inputs.features
    def set_features(self, features: AttributeList) -> None:
        if features and not self.features:
            # if features are on the input and they were not before
            # context should be saved for later when features will not be
            # present anymore
            self.closeContext()
        self.features = features
        if self.data:
            self.set_attributes()
            self.update_plots()

    def set_attributes(self) -> None:
        """
        In case when features present: set shown attributes to match features
        In case when features not present: set default value and open context
        """
        self.closeContext()
        if self.features:
            self.attrs = [
                [f]
                for f in self.features
                if f in self.data.domain and f != self.data.time_variable
            ]
            self.is_logit = [False] * len(self.attrs)
        else:
            variables = [
                var
                for var in self.data.domain.variables
                if var.is_continuous and var != self.data.time_variable
            ]
            self.attrs = [[variables[0]]]
            self.is_logit = [False]
            # context is only open when features not provided on input
            # when provided features defines the selection
            self.openContext(self.data.domain)

    def update_plots(self) -> None:
        """
        Update plots when new data or new selection comes
        """
        # remove plots if too many of them
        while len(self.configs) > len(self.attrs):
            plot = self.configs[-1]
            plot.sigClosed.emit(plot.ax, plot)

        # add plots if not enough of them
        while len(self.configs) < len(self.attrs):
            self.add_plot()

        assert len(self.configs) == len(self.attrs)
        assert len(self.attrs) == len(self.is_logit)
        # select correct values
        for config, attr, log in zip(self.configs, self.attrs, self.is_logit):
            config.set_logarithmic(log)
            config.set_selection(attr)
            config.view.setEnabled(not self.features)

    def _selections_changed(self) -> None:
        for config in self.configs:
            config.selection_changed()

    def closeEvent(self, event: QCloseEvent) -> None:
        """
        When someone delets the widget closeContext must be called to gather
        settings.
        """
        self.closeContext()
        super().closeEvent(event)

    def closeContext(self) -> None:
        """
        Gather configs in contextVariables and close context.
        """
        if not self.features:
            # only close in case of when features are not present if they are
            # feature selection is defined by the input and context should
            # not have impact
            attrs, is_logit = [], []
            for config in self.configs:
                attrs.append(config.get_selection())
                is_logit.append(config.is_logarithmic)
            self.attrs = attrs
            self.is_logit = is_logit
            super().closeContext()


if __name__ == "__main__":
    from orangecontrib.timeseries import ARIMA, VAR

    airpassengers = Timeseries.from_file('airpassengers')
    msft = airpassengers.interp()
    model1 = ARIMA((3, 1, 1)).fit(airpassengers)
    model2 = VAR(4).fit(msft)
    ow = WidgetPreview(OWLineChart)
    ow.run(
        set_data=airpassengers,
        set_forecast=[
            (model1.predict(10, as_table=True), 0),
            (model2.predict(10, as_table=True), 1)
        ]
    )
