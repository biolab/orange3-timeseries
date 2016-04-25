from datetime import datetime
from enum import Enum
from itertools import chain
from numbers import Number
from collections import defaultdict

import scipy.stats

import numpy as np

from PyQt4.QtGui import QListView

from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.colorpalette import GradientPaletteGenerator
from Orange.widgets.utils.itemmodels import VariableListModel

from orangecontrib.timeseries import Timeseries
from Orange.widgets.highcharts import Highchart


class Spiralogram(Highchart):
    """
    A radial heatmap.

    Fiddle with it: https://jsfiddle.net/4v87fo2q/5/
    https://jsfiddle.net/avxg2za9/1/
    """

    class AxesCategories(Enum):
        YEARS = ('', lambda d: d.year)
        MONTHS = ('', lambda d: d.month)
        DAYS = ('', lambda d: d.day)
        MONTHS_OF_YEAR =  (tuple(range(1, 13)),  lambda d: d.month)
        DAYS_OF_WEEK =    (tuple(range(0, 7)),   lambda d: d.weekday())
        DAYS_OF_MONTH =   (tuple(range(1, 32)),  lambda d: d.day)
        DAYS_OF_YEAR =    (tuple(range(1, 367)), lambda d: d.timetuple().tm_yday)
        WEEKS_OF_YEAR =   (tuple(range(1, 54)),  lambda d: d.isocalendar()[1])
        WEEKS_OF_MONTH =  (tuple(range(1, 6)),   lambda d: int(np.ceil((d + d.replace(day=1).weekday()) / 7)))
        HOURS_OF_DAY =    (tuple(range(24)),     lambda d: d.hour)
        MINUTES_OF_HOUR = (tuple(range(60)),     lambda d: d.minute)

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
        # TODO: support discrete variables
        if isinstance(xdim, str) and xdim.isdigit():
            xdim = [str(i) for i in range(1, int(xdim) + 1)]
        if isinstance(ydim, str) and ydim.isdigit():
            ydim = [str(i) for i in range(1, int(ydim) + 1)]

        xvals, xfunc = xdim.value
        yvals, yfunc = ydim.value

        values = timeseries[:, attr].X
        time_values = timeseries[:, timeseries.time_variable].X.ravel()

        if True:
            fromtimestamp = datetime.fromtimestamp
            time_values = [fromtimestamp(i) for i in time_values]

        if not yvals:
            yvals = sorted(set(yfunc(i) for i in time_values))
        if not xvals:
            xvals = sorted(set(xfunc(i) for i in time_values))

        indices = defaultdict(list)
        for i, tval in enumerate(time_values):
            indices[(xfunc(tval), yfunc(tval))].append(i)

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
                        aggval = fagg(values[inds])
                    except ValueError:
                        aggval = np.nan
                else:
                    aggval = np.nan
                if np.isnan(aggval):
                    aggval = 'NaN'
                    point['select'] = ''
                    point['color'] = 'white'
                else:
                    aggvals.append(aggval)
                point['n'] = aggval

        maxval, minval = np.max(aggvals), np.min(aggvals)
        ptpval = maxval - minval
        color = GradientPaletteGenerator('#ffcccc', '#cc0000')
        for serie in series:
            for point in serie['data']:
                n = point['n']
                if isinstance(n, Number):
                    point['color'] = color[(n - minval) / ptpval]

        self.chart(series=series,
                   xAxis_categories=[xname(i) for i in xvals],
                   yAxis_categories=[yname(i) for i in reversed(yvals)])

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
                tooltip=dict(
                    headerFormat=('<span style="font-size:13pt;color:{point.color}">\u25A0</span> '
                                  '{series.name}, {point.key}:'),
                    pointFormat=' <b>{point.n}</b><br/>',
                ),
                states=dict(
                    select=dict(
                        borderColor=None,  # Revert Orange's theme
                    )
                )
            )
        ),
        tooltip=dict(
            shared=False,

        )
        # series=[]  # Override this
    )

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args,
                         options=self.OPTIONS,
                         enable_select='+',  # TODO: implement mouse-drag select
                         **kwargs)
        self.indices = {}



class AggregateFunctions(Enum):
    """Aggregation functions.

    Wrapped in tuples because silly Enum doesn't consider methods as members.
    """
    SUM = (lambda arr: np.nansum(arr),)
    COUNT_NONZERO = (lambda arr: np.count_nonzero(arr[~np.isnan(arr)]),)
    MAX = (lambda arr: np.nanmax(arr),)
    MIN = (lambda arr: np.nanmin(arr),)
    MEAN = (lambda arr: np.nanmean(arr),)
    MEDIAN = (lambda arr: np.nanmedian(arr),)
    VARIANCE = (lambda arr: np.nanvar(arr),)
    STDDEV = (lambda arr: np.nanstd(arr),)
    MODE = (lambda arr: scipy.stats.mode(arr, nan_policy='omit').mode[0],)
    PRODUCT = (lambda arr: np.nanprod(arr),)
    HARMONIC_MEAN = (lambda arr: scipy.stats.hmean(arr[arr > 0], axis=None),)
    GEOMETRIC_MEAN = (lambda arr: scipy.stats.gmean(arr[~np.isnan(arr) & (arr != 0)], axis=None),)


def _enum_str(enum_value, inverse=False):
    if inverse:
        return enum_value.replace(' ', '_').upper()
    return enum_value.name.replace('_', ' ').lower()


class OWSpiralogram(widget.OWWidget):
    name = 'Spiralogram'
    description = "Visualize time series' periodicity in a spiral heatmap."
    icon = 'icons/Spiralogram.svg'
    priority = 120

    inputs = [("Time series", Timeseries, 'set_data')]
    outputs = [("Time series", Timeseries)]

    ax1 = settings.Setting('months of year')
    ax2 = settings.Setting('years')
    agg_attr = settings.Setting([])
    agg_func_i = settings.Setting(0)

    MODE_INDEX = list(AggregateFunctions).index(AggregateFunctions.MODE)

    def __init__(self):
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
            box, self, 'agg_func_i', label='Function:', orientation='horizontal',
            items=tuple(_enum_str(i) for i in AggregateFunctions),
            callback=self.replot)
        self.attrlist_model = VariableListModel(parent=self)
        self.attrlist = QListView(selectionMode=QListView.ExtendedSelection)
        self.attrlist.setModel(self.attrlist_model)
        self.attrlist.selectionModel().selectionChanged.connect(
            self.attrlist_selectionChanged)
        box.layout().addWidget(self.attrlist)
        gui.rubber(self.controlArea)
        self.chart = chart = Spiralogram(self, self,
                                         selection_callback=self.on_selection,
                                         debug=True
                                         )
        self.mainArea.layout().addWidget(chart)
        chart.chart()

    def attrlist_selectionChanged(self):
        self.agg_attr = [self.attrlist_model[i.row()]
                         for i in self.attrlist.selectionModel().selectedIndexes()]
        self.replot()

    def set_data(self, data):
        self.data = data

        def init_combos():
            for combo in (self.combo_ax1, self.combo_ax2):
                combo.clear()
            self.attrlist_model[:] = []
            for i in Spiralogram.AxesCategories:
                for combo in (self.combo_ax1, self.combo_ax2):
                    combo.addItem(_enum_str(i))
            for var in data.domain if data is not None else []:
                if var.is_primitive() and var is not data.time_variable:
                    self.attrlist_model.append(var)
                if var.is_discrete:
                    for combo in (self.combo_ax1, self.combo_ax2):
                        combo.addItem(gui.attributeIconDict[var], var.name)

        init_combos()
        self.chart.clear()

        if data is None:
            self.commit()
            return

    def replot(self):
        vars = self.agg_attr
        # TODO test discrete
        if (any(var.is_discrete for var in vars) and
            self.agg_func_i != self.MODE_INDEX):
            self.combo_func.setCurrentIndex(self.MODE_INDEX)
            return
        try:
            ax1 = Spiralogram.AxesCategories[_enum_str(self.ax1, True)]
        except KeyError:
            ax1 = self.data.domain[self.ax1]
        try:
            ax2 = Spiralogram.AxesCategories[_enum_str(self.ax2, True)]
        except KeyError:
            ax2 = self.data.domain[self.ax2]
        func = list(AggregateFunctions)[self.agg_func_i].value[0]
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
    ow.set_data(Timeseries('autoroute'))

    ow.show()
    a.exec()
