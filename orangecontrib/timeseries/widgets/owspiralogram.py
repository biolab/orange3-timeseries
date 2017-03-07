from datetime import datetime
from enum import Enum
from itertools import chain
from numbers import Number
from collections import defaultdict
from os import path

import numpy as np
from Orange.util import color_to_hex

from Orange.data import Table, Domain, TimeVariable, DiscreteVariable
from Orange.widgets import widget, gui, settings
from Orange.widgets.highcharts import Highchart
from Orange.widgets.utils.colorpalette import GradientPaletteGenerator
from Orange.widgets.utils.itemmodels import VariableListModel

from orangecontrib.timeseries.widgets.utils import ListModel
from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.agg_funcs import AGG_FUNCTIONS, Mode

from PyQt4.QtGui import QListView, QItemSelectionModel
from PyQt4.QtGui import QColor

class Spiralogram(Highchart):
    """
    A radial heatmap.

    Fiddle with it: https://jsfiddle.net/4v87fo2q/5/
    https://jsfiddle.net/avxg2za9/1/
    """

    class AxesCategories(Enum):
        YEARS =  ('', lambda _, d: d.year)
        MONTHS = ('', lambda _, d: d.month)
        DAYS =   ('', lambda _, d: d.day)
        MONTHS_OF_YEAR =  (tuple(range(1, 13)),  lambda _, d: d.month)
        DAYS_OF_WEEK =    (tuple(range(0, 7)),   lambda _, d: d.weekday())
        DAYS_OF_MONTH =   (tuple(range(1, 32)),  lambda _, d: d.day)
        DAYS_OF_YEAR =    (tuple(range(1, 367)), lambda _, d: d.timetuple().tm_yday)
        WEEKS_OF_YEAR =   (tuple(range(1, 54)),  lambda _, d: d.isocalendar()[1])
        WEEKS_OF_MONTH =  (tuple(range(1, 6)),   lambda _, d: int(np.ceil((d.day + d.replace(day=1).weekday()) / 7)))
        HOURS_OF_DAY =    (tuple(range(24)),     lambda _, d: d.hour)
        MINUTES_OF_HOUR = (tuple(range(60)),     lambda _, d: d.minute)

        @staticmethod
        def month_name(month):
            return ('January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November', 'December')[month - 1]

        @staticmethod
        def weekday_name(weekday):
            return ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')[weekday]

        @classmethod
        def name_it(cls, dim):
            if dim == cls.MONTHS_OF_YEAR:
                return lambda val: cls.month_name(val)
            if dim == cls.DAYS_OF_WEEK:
                return lambda val: cls.weekday_name(val)
            return lambda val: val

    def setSeries(self, timeseries, attr, xdim, ydim, fagg):
        if timeseries is None or not attr:
            self.clear()
            return
        if isinstance(xdim, str) and xdim.isdigit():
            xdim = [str(i) for i in range(1, int(xdim) + 1)]
        if isinstance(ydim, str) and ydim.isdigit():
            ydim = [str(i) for i in range(1, int(ydim) + 1)]

        if isinstance(xdim, DiscreteVariable):
            xcol = timeseries.get_column_view(xdim)[0]
            xvals, xfunc = xdim.values, lambda i, _: xdim.repr_val(xcol[i])
        else:
            xvals, xfunc = xdim.value
        if isinstance(ydim, DiscreteVariable):
            ycol = timeseries.get_column_view(ydim)[0]
            yvals, yfunc = ydim.values, lambda i, _: ydim.repr_val(ycol[i])
        else:
            yvals, yfunc = ydim.value

        attr = attr[0]
        values = timeseries.get_column_view(attr)[0]
        time_values = timeseries.time_values

        if True:
            fromtimestamp = datetime.fromtimestamp
            time_values = [fromtimestamp(i) for i in time_values]

        if not yvals:
            yvals = sorted(set(yfunc(i, v) for i, v in enumerate(time_values)))
        if not xvals:
            xvals = sorted(set(xfunc(i, v) for i, v in enumerate(time_values)))

        indices = defaultdict(list)
        for i, tval in enumerate(time_values):
            indices[(xfunc(i, tval), yfunc(i, tval))].append(i)

        series = []
        aggvals = []
        self.indices = []
        xname = self.AxesCategories.name_it(xdim)
        yname = self.AxesCategories.name_it(ydim)
        for yval in yvals:
            data = []
            series.append(dict(name=yname(yval), data=data))
            self.indices.append([])
            for xval in xvals:
                inds = indices.get((xval, yval), ())
                self.indices[-1].append(inds)
                point = dict(y=1)
                data.append(point)
                if inds:
                    try:
                        aggval = np.round(fagg(values[inds]), 4)
                    except ValueError:
                        aggval = np.nan
                else:
                    aggval = np.nan
                if isinstance(aggval, Number) and np.isnan(aggval):
                    aggval = 'N/A'
                    point['select'] = ''
                    point['color'] = 'white'
                else:
                    aggvals.append(aggval)
                point['n'] = aggval

        # TODO: allow scaling over just rows or cols instead of all values as currently
        try:
            maxval, minval = np.max(aggvals), np.min(aggvals)
        except ValueError:
            self.clear()
            return
        ptpval = maxval - minval
        color = GradientPaletteGenerator('#ffcccc', '#cc0000')
        selected_color = GradientPaletteGenerator('#cdd1ff', '#0715cd')
        for serie in series:
            for point in serie['data']:
                n = point['n']
                if isinstance(n, Number):
                    val = (n - minval) / ptpval

                    if attr.is_discrete:
                        point['n'] = attr.repr_val(n)
                    elif isinstance(attr, TimeVariable):
                        point['n'] = attr.repr_val(n)

                    if attr.is_discrete:
                        point['color'] = color = color_to_hex(attr.colors[int(n)])
                        sel_color = QColor(color).darker(150).name()
                    else:
                        point['color'] = color[val]
                        sel_color = selected_color[val]
                    point['states'] = dict(select=dict(borderColor="black",
                                                       color=sel_color))

        # TODO: make a white hole in the middle. Center w/o data.
        self.chart(series=series,
                   xAxis_categories=[xname(i) for i in xvals],
                   yAxis_categories=[yname(i) for i in reversed(yvals)],
                   javascript_after='''
                       // Force zoomType which is by default disabled for polar charts
                       chart.options.chart.zoomType = 'xy';
                       chart.pointer.init(chart, chart.options);
                   ''')

    def selection_indices(self, indices):
        result = []
        for i, inds in enumerate(indices):
            if len(inds):
                for j in inds:
                    result.append(self.indices[i][j])
        return sorted(chain.from_iterable(result))

    OPTIONS = dict(
        chart=dict(
            type='column',
            polar=True,
            panning=False,  # Fixes: https://github.com/highcharts/highcharts/issues/5240
            events=dict(
                selection='/**/ zoomSelection',  # from _spiralogram.js
            ),
            zoomType='xy',  # polar=True disabled this, but is again reenabled in JS after chart init
        ),
        legend=dict(
            enabled=False,  # FIXME: Have a heatmap-style legend
        ),
        xAxis=dict(
            gridLineWidth=0,
            showLastLabel=False,
            # categories=None,  # Override this
        ),
        yAxis=dict(
            gridLineWidth=0,
            endOnTick=False,
            showLastLabel=False,
            # categories=None,  # Override this
            labels=dict(
                y=0,
                align='center',
                style=dict(
                    color='black',
                    fontWeight='bold',
                    textShadow=('2px  2px 1px white, -2px  2px 1px white,'
                                '2px -2px 1px white, -2px -2px 1px white'),
                ),
            ),
        ),
        plotOptions=dict(
            column=dict(
                colorByPoint=True,
                stacking='normal',
                pointPadding=0,
                groupPadding=0,
                borderWidth=2,
                pointPlacement='on',
                allowPointSelect=True,
                states=dict(
                    select=dict(
                        borderColor=None,  # Revert Orange's theme
                    )
                )
            )
        ),
        tooltip=dict(
            shared=False,
            formatter=('''/**/
                (function() {
                    if (this.point.n == "N/A")
                        return false;
                    return '<span style="font-size:13pt;color:' + \
                           this.point.color + '">\u25A0</span> ' + \
                           this.series.name + ', ' + \
                           this.x + ': <b>' + \
                           this.point.n + '</b><br/>';
                })
            '''),
        )
        # series=[]  # Override this
    )

    def __init__(self, parent, *args, **kwargs):
        # TODO: Add colorAxes (heatmap legend)
        with open(path.join(path.dirname(__file__), '_spiralogram.js')) as f:
            javascript = f.read()
        super().__init__(parent, *args,
                         options=self.OPTIONS,
                         enable_select='+',  # TODO: implement mouse-drag select
                         javascript=javascript,
                         **kwargs)
        self.indices = {}


def _enum_str(enum_value, inverse=False):
    if inverse:
        return enum_value.replace(' ', '_').upper()
    return enum_value.name.replace('_', ' ').lower()


class OWSpiralogram(widget.OWWidget):
    name = 'Spiralogram'
    description = "Visualize time series' periodicity in a spiral heatmap."
    icon = 'icons/Spiralogram.svg'
    priority = 120

    inputs = [("Time series", Table, 'set_data')]
    outputs = [("Time series", Timeseries)]

    settingsHandler = settings.DomainContextHandler()

    ax1 = settings.ContextSetting('months of year')
    ax2 = settings.ContextSetting('years')
    agg_attr = settings.ContextSetting([])
    agg_func = settings.ContextSetting(0)

    def __init__(self):
        self.data = None
        self.indices = []
        box = gui.vBox(self.controlArea, 'Axes')
        self.combo_ax2 = gui.comboBox(
            box, self, 'ax2', label='Y axis:', callback=self.replot,
            sendSelectedValue=True, orientation='horizontal')
        self.combo_ax1 = gui.comboBox(
            box, self, 'ax1', label='Radial:', callback=self.replot,
            sendSelectedValue=True, orientation='horizontal')
        box = gui.vBox(self.controlArea, 'Aggregation')
        self.combo_func = gui.comboBox(
            box, self, 'agg_func', label='Function:', orientation='horizontal',
            callback=self.replot)
        func_model = ListModel(AGG_FUNCTIONS, parent=self)
        self.combo_func.setModel(func_model)

        self.attrlist_model = VariableListModel(parent=self)
        self.attrlist = QListView(selectionMode=QListView.SingleSelection)
        self.attrlist.setModel(self.attrlist_model)
        self.attrlist.selectionModel().selectionChanged.connect(
            self.attrlist_selectionChanged)
        box.layout().addWidget(self.attrlist)
        gui.rubber(self.controlArea)
        self.chart = chart = Spiralogram(self,
                                         selection_callback=self.on_selection)
        self.mainArea.layout().addWidget(chart)

    def attrlist_selectionChanged(self):
        self.agg_attr = [self.attrlist_model[i.row()]
                         for i in self.attrlist.selectionModel().selectedIndexes()]
        self.replot()

    def set_data(self, data):
        self.data = data = None if data is None else Timeseries.from_data_table(data)

        def init_combos():
            for combo in (self.combo_ax1, self.combo_ax2):
                combo.clear()
            newmodel = []
            if data is not None and data.time_variable is not None:
                for i in Spiralogram.AxesCategories:
                    for combo in (self.combo_ax1, self.combo_ax2):
                        combo.addItem(_enum_str(i))
            for var in data.domain if data is not None else []:
                if (var.is_primitive() and
                        (var is not data.time_variable or
                         isinstance(var, TimeVariable) and data.time_delta is None)):
                    newmodel.append(var)
                if var.is_discrete:
                    for combo in (self.combo_ax1, self.combo_ax2):
                        combo.addItem(gui.attributeIconDict[var], var.name)
            self.attrlist_model.wrap(newmodel)

        init_combos()
        self.chart.clear()

        if data is None:
            self.commit()
            return

        self.closeContext()
        self.ax2 = next((self.combo_ax2.itemText(i)
                         for i in range(self.combo_ax2.count())), '')
        self.ax1 = next((self.combo_ax1.itemText(i)
                         for i in range(1, self.combo_ax1.count())), self.ax2)
        self.agg_attr = [data.domain[0]] if len(data.domain) else []
        self.agg_func = 0
        self.openContext(data.domain)

        if self.agg_attr:
            self.attrlist.blockSignals(True)
            self.attrlist.selectionModel().clear()
            for attr in self.agg_attr:
                try:
                    row = self.attrlist_model.indexOf(attr)
                except ValueError:
                    continue
                self.attrlist.selectionModel().select(
                    self.attrlist_model.index(row),
                    QItemSelectionModel.SelectCurrent)
            self.attrlist.blockSignals(False)

        self.replot()

    def replot(self):
        if not self.combo_ax1.count() or not self.agg_attr:
            return self.chart.clear()

        vars = self.agg_attr
        func = AGG_FUNCTIONS[self.agg_func]
        if any(var.is_discrete for var in vars) and func != Mode:
            self.combo_func.setCurrentIndex(AGG_FUNCTIONS.index(Mode))
            func = Mode
        try:
            ax1 = Spiralogram.AxesCategories[_enum_str(self.ax1, True)]
        except KeyError:
            ax1 = self.data.domain[self.ax1]
        # TODO: Allow having only a sinle (i.e. radial) axis
        try:
            ax2 = Spiralogram.AxesCategories[_enum_str(self.ax2, True)]
        except KeyError:
            ax2 = self.data.domain[self.ax2]
        self.chart.setSeries(self.data, vars, ax1, ax2, func)

    def on_selection(self, indices):
        self.indices = self.chart.selection_indices(indices)
        self.commit()

    def commit(self):
        self.send('Time series', self.data[self.indices] if self.data else None)


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication

    a = QApplication([])
    ow = OWSpiralogram()
    ow.set_data(Table('cyber-security-breaches'))

    ow.show()
    a.exec()
