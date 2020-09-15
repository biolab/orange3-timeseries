from enum import Enum
from itertools import chain
from numbers import Number
from collections import defaultdict
from os import path

import numpy as np

from Orange.data import Table, TimeVariable, DiscreteVariable
from Orange.util import color_to_hex
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.colorpalettes import ContinuousPalette
from Orange.widgets.utils.itemmodels import VariableListModel
from orangewidget.utils.widgetpreview import WidgetPreview
from Orange.widgets.widget import Input, Output
from orangecontrib.timeseries import Timeseries, fromtimestamp
from orangecontrib.timeseries.agg_funcs import AGG_OPTIONS, Mode
from orangecontrib.timeseries.widgets.highcharts import Highchart

red_palette = ContinuousPalette('Linear Red', 'linear_red',
                                [[204, 0, 0], [204, 1, 0], [204, 1, 1], [204, 2, 2], [204, 3, 3], [205, 4, 4], [205, 5, 4], [205, 5, 5], [205, 6, 6], [205, 7, 7], [206, 8, 8], [206, 9, 8], [206, 9, 9], [206, 10, 10], [206, 11, 11], [207, 12, 12], [207, 13, 12], [207, 13, 13], [207, 14, 14], [207, 15, 15], [208, 16, 16], [208, 17, 16], [208, 17, 17], [208, 18, 18], [208, 19, 19], [209, 20, 20], [209, 21, 20], [209, 21, 21], [209, 22, 22], [209, 23, 23], [210, 24, 24], [210, 25, 24], [210, 25, 25], [210, 26, 26], [210, 27, 27], [211, 28, 28], [211, 29, 28], [211, 29, 29], [211, 30, 30], [211, 31, 31], [212, 32, 32], [212, 33, 32], [212, 33, 33], [212, 34, 34], [212, 35, 35], [213, 36, 36], [213, 37, 36], [213, 37, 37], [213, 38, 38], [213, 39, 39], [214, 40, 40], [214, 41, 40], [214, 41, 41], [214, 42, 42], [214, 43, 43], [215, 44, 44], [215, 45, 44], [215, 45, 45], [215, 46, 46], [215, 47, 47], [216, 48, 48], [216, 49, 48], [216, 49, 49], [216, 50, 50], [216, 51, 51], [217, 52, 52], [217, 53, 52], [217, 53, 53], [217, 54, 54], [217, 55, 55], [218, 56, 56], [218, 57, 56], [218, 57, 57], [218, 58, 58], [218, 59, 59], [219, 60, 60], [219, 61, 60], [219, 61, 61], [219, 62, 62], [219, 63, 63], [220, 64, 64], [220, 65, 64], [220, 65, 65], [220, 66, 66], [220, 67, 67], [221, 68, 68], [221, 69, 68], [221, 69, 69], [221, 70, 70], [221, 71, 71], [222, 72, 72], [222, 73, 72], [222, 73, 73], [222, 74, 74], [222, 75, 75], [223, 76, 76], [223, 77, 76], [223, 77, 77], [223, 78, 78], [223, 79, 79], [224, 80, 80], [224, 81, 80], [224, 81, 81], [224, 82, 82], [224, 83, 83], [225, 84, 84], [225, 85, 84], [225, 85, 85], [225, 86, 86], [225, 87, 87], [226, 88, 88], [226, 89, 88], [226, 89, 89], [226, 90, 90], [226, 91, 91], [227, 92, 92], [227, 93, 92], [227, 93, 93], [227, 94, 94], [227, 95, 95], [228, 96, 96], [228, 97, 96], [228, 97, 97], [228, 98, 98], [228, 99, 99], [229, 100, 100], [229, 101, 100], [229, 101, 101], [229, 102, 102], [229, 103, 103], [230, 104, 104], [230, 105, 104], [230, 105, 105], [230, 106, 106], [230, 107, 107], [231, 108, 108], [231, 109, 108], [231, 109, 109], [231, 110, 110], [231, 111, 111], [232, 112, 112], [232, 113, 112], [232, 113, 113], [232, 114, 114], [232, 115, 115], [233, 116, 116], [233, 117, 116], [233, 117, 117], [233, 118, 118], [233, 119, 119], [234, 120, 120], [234, 121, 120], [234, 121, 121], [234, 122, 122], [234, 123, 123], [235, 124, 124], [235, 125, 124], [235, 125, 125], [235, 126, 126], [235, 127, 127], [236, 128, 128], [236, 129, 128], [236, 129, 129], [236, 130, 130], [236, 131, 131], [237, 132, 132], [237, 133, 132], [237, 133, 133], [237, 134, 134], [237, 135, 135], [238, 136, 136], [238, 137, 136], [238, 137, 137], [238, 138, 138], [238, 139, 139], [239, 140, 140], [239, 141, 140], [239, 141, 141], [239, 142, 142], [239, 143, 143], [240, 144, 144], [240, 145, 144], [240, 145, 145], [240, 146, 146], [240, 147, 147], [241, 148, 148], [241, 149, 148], [241, 149, 149], [241, 150, 150], [241, 151, 151], [242, 152, 152], [242, 153, 152], [242, 153, 153], [242, 154, 154], [242, 155, 155], [243, 156, 156], [243, 157, 156], [243, 157, 157], [243, 158, 158], [243, 159, 159], [244, 160, 160], [244, 161, 160], [244, 161, 161], [244, 162, 162], [244, 163, 163], [245, 164, 164], [245, 165, 164], [245, 165, 165], [245, 166, 166], [245, 167, 167], [246, 168, 168], [246, 169, 168], [246, 169, 169], [246, 170, 170], [246, 171, 171], [247, 172, 172], [247, 173, 172], [247, 173, 173], [247, 174, 174], [247, 175, 175], [248, 176, 176], [248, 177, 176], [248, 177, 177], [248, 178, 178], [248, 179, 179], [249, 180, 180], [249, 181, 180], [249, 181, 181], [249, 182, 182], [249, 183, 183], [250, 184, 184], [250, 185, 184], [250, 185, 185], [250, 186, 186], [250, 187, 187], [251, 188, 188], [251, 189, 188], [251, 189, 189], [251, 190, 190], [251, 191, 191], [252, 192, 192], [252, 193, 192], [252, 193, 193], [252, 194, 194], [252, 195, 195], [253, 196, 196], [253, 197, 196], [253, 197, 197], [253, 198, 198], [253, 199, 199], [254, 200, 200], [254, 201, 200], [254, 201, 201], [254, 202, 202], [254, 203, 203], [255, 204, 204]]
                                )


class Spiralogram(Highchart):
    """
    A radial heatmap.

    Fiddle with it: https://jsfiddle.net/4v87fo2q/5/
    https://jsfiddle.net/avxg2za9/1/
    """

    class AxesCategories(Enum):
        YEARS = ('', lambda _, d: d.year)
        MONTHS = ('', lambda _, d: d.month)
        DAYS = ('', lambda _, d: d.day)
        MONTHS_OF_YEAR = (tuple(range(1, 13)), lambda _, d: d.month)
        DAYS_OF_WEEK = (tuple(range(0, 7)), lambda _, d: d.weekday())
        DAYS_OF_MONTH = (tuple(range(1, 32)), lambda _, d: d.day)
        DAYS_OF_YEAR = (
        tuple(range(1, 367)), lambda _, d: d.timetuple().tm_yday)
        WEEKS_OF_YEAR = (tuple(range(1, 54)), lambda _, d: d.isocalendar()[1])
        WEEKS_OF_MONTH = (tuple(range(1, 6)), lambda _, d: int(
            np.ceil((d.day + d.replace(day=1).weekday()) / 7)))
        HOURS_OF_DAY = (tuple(range(24)), lambda _, d: d.hour)
        MINUTES_OF_HOUR = (tuple(range(60)), lambda _, d: d.minute)

        @staticmethod
        def month_name(month):
            return ('January', 'February', 'March', 'April', 'May', 'June',
                    'July', 'August', 'September', 'October', 'November',
                    'December')[month - 1]

        @staticmethod
        def weekday_name(weekday):
            return (
            'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday',
            'Sunday')[weekday]

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

        values = timeseries.get_column_view(attr)[0]
        time_values = [fromtimestamp(i, tz=timeseries.time_variable.timezone)
                       for i in timeseries.time_values]

        if not yvals:
            yvals = sorted(set(yfunc(i, v) for i, v in enumerate(time_values) if
                               v is not None))
        if not xvals:
            xvals = sorted(set(xfunc(i, v) for i, v in enumerate(time_values) if
                               v is not None))

        indices = defaultdict(list)
        for i, tval in enumerate(time_values):
            if tval is not None:
                indices[(xfunc(i, tval), yfunc(i, tval))].append(i)

        if self._owwidget.invert_date_order:
            yvals = yvals[::-1]

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
        color = red_palette
        for serie in series:
            for point in serie['data']:
                n = point['n']
                if isinstance(n, Number):
                    val = (n - minval) / ptpval

                    if attr.is_discrete and fagg == Mode:
                        point['n'] = attr.repr_val(n)
                    elif isinstance(attr, TimeVariable):
                        point['n'] = attr.repr_val(n)

                    point['color'] = color_to_hex(attr.colors[int(n)]) if \
                        attr.is_discrete else color[val]
                    point['states'] = dict(select=dict(borderColor="black"))

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
            panning=False, # Fixes: https://github.com/highcharts/highcharts/issues/5240
            events=dict(
                selection='/**/ zoomSelection',  # from _spiralogram.js
            ),
            zoomType='xy',
            # polar=True disabled this, but is again reenabled in JS after chart init
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
        assert isinstance(parent, widget.OWWidget)
        self._owwidget = parent


def _enum_str(enum_value, inverse=False):
    if isinstance(enum_value, DiscreteVariable):
        enum_value = str(enum_value)
    if inverse:
        return enum_value.replace(' ', '_').upper()
    return enum_value.name.replace('_', ' ').lower()


DEFAULT_AGG_FUNC = next(iter(AGG_OPTIONS.keys()))


class OWSpiralogram(widget.OWWidget):
    name = 'Spiralogram'
    description = "Visualize time series' periodicity in a spiral heatmap."
    icon = 'icons/Spiralogram.svg'
    priority = 120

    class Inputs:
        time_series = Input("Time series", Table)

    class Outputs:
        time_series = Output("Time series", Timeseries)

    settings_version = 2
    settingsHandler = settings.DomainContextHandler()

    ax1 = settings.ContextSetting('months of year')
    ax2 = settings.ContextSetting('years')

    agg_attr = settings.ContextSetting(None)
    agg_func = settings.ContextSetting(DEFAULT_AGG_FUNC)

    invert_date_order = settings.Setting(False)

    graph_name = 'chart'

    class Error(widget.OWWidget.Error):
        no_time_variable = widget.Msg(
            'Spiralogram requires time series with a time variable.')

    def __init__(self):
        self.data = None
        self.indices = []
        box = gui.vBox(self.controlArea, 'Axes')
        self.combo_ax2_model = VariableListModel(parent=self)
        self.combo_ax1_model = VariableListModel(parent=self)
        for model in (self.combo_ax1_model, self.combo_ax2_model):
            model[:] = [_enum_str(i) for i in Spiralogram.AxesCategories]
        self.combo_ax2 = gui.comboBox(
            box, self, 'ax2', label='Y axis:', callback=self.replot,
            sendSelectedValue=True, orientation='horizontal',
            model=self.combo_ax2_model)
        self.combo_ax1 = gui.comboBox(
            box, self, 'ax1', label='Radial:', callback=self.replot,
            sendSelectedValue=True, orientation='horizontal',
            model=self.combo_ax1_model)
        gui.checkBox(box, self, 'invert_date_order', 'Invert Y axis order',
                     callback=self.replot)

        box = gui.vBox(self.controlArea, 'Aggregation')

        self.attrs_model = VariableListModel()
        self.attr_cb = gui.comboBox(box, self, 'agg_attr',
                                    sendSelectedValue=True,
                                    model=self.attrs_model,
                                    callback=self.update_agg_combo)

        self.combo_func = gui.comboBox(
            box, self, 'agg_func', label='Function:',
            items=[DEFAULT_AGG_FUNC], orientation='horizontal',
            sendSelectedValue=True,
            callback=self.replot)

        gui.rubber(self.controlArea)

        self.chart = chart = Spiralogram(self,
                                         selection_callback=self.on_selection)
        self.mainArea.layout().addWidget(chart)

    @Inputs.time_series
    def set_data(self, data):
        self.Error.clear()
        self.data = data = None if data is None else \
                           Timeseries.from_data_table(data)

        if data is None:
            self.commit()
            return

        if self.data.time_variable is None or not isinstance(
                self.data.time_variable, TimeVariable):
            self.Error.no_time_variable()
            self.commit()
            return

        def init_combos():
            for model in (self.combo_ax1_model, self.combo_ax2_model):
                model.clear()
            variables = []
            if data is not None and data.time_variable is not None:
                for model in (self.combo_ax1_model, self.combo_ax2_model):
                    model[:] = [_enum_str(i) for i in
                                Spiralogram.AxesCategories]
            for var in data.domain.variables if data is not None else []:
                if (var.is_primitive() and
                        (var is not data.time_variable or
                         isinstance(var, TimeVariable)
                         and data.time_delta.backwards_compatible_delta is None)):
                    variables.append(var)

                if var.is_discrete:
                    for model in (self.combo_ax1_model, self.combo_ax2_model):
                        model.append(var)
            self.attrs_model[:] = variables

        init_combos()
        self.chart.clear()

        self.closeContext()
        self.ax2 = next((self.combo_ax2.itemText(i)
                         for i in range(self.combo_ax2.count())), '')
        self.ax1 = next((self.combo_ax1.itemText(i)
                         for i in range(1, self.combo_ax1.count())), self.ax2)
        self.agg_attr = data.domain[self.attrs_model[0]] if len(
            data.domain.variables) else None
        self.agg_func = DEFAULT_AGG_FUNC

        if getattr(data, 'time_variable', None) is not None:
            self.openContext(data.domain)

        self.update_agg_combo()
        self.replot()

    def update_agg_combo(self):
        self.combo_func.clear()
        new_aggs = AGG_OPTIONS

        if self.agg_attr is not None:
            if self.agg_attr.is_discrete:
                new_aggs = [agg for agg in AGG_OPTIONS if AGG_OPTIONS[agg].disc]
            elif self.agg_attr.is_time:
                new_aggs = [agg for agg in AGG_OPTIONS if AGG_OPTIONS[agg].time]
        self.combo_func.addItems(new_aggs)

        if self.agg_func not in new_aggs:
            self.agg_func = next(iter(new_aggs))

        self.replot()

    def replot(self):
        if not self.combo_ax1.count() or not self.agg_attr:
            return self.chart.clear()

        func = AGG_OPTIONS[self.agg_func].transform
        try:
            ax1 = Spiralogram.AxesCategories[_enum_str(self.ax1, True)]
        except KeyError:
            ax1 = self.data.domain[self.ax1]
        # TODO: Allow having only a single (i.e. radial) axis
        try:
            ax2 = Spiralogram.AxesCategories[_enum_str(self.ax2, True)]
        except KeyError:
            ax2 = self.data.domain[self.ax2]
        self.chart.setSeries(self.data, self.agg_attr, ax1, ax2, func)

    def on_selection(self, indices):
        self.indices = self.chart.selection_indices(indices)
        self.commit()

    def commit(self):
        self.Outputs.time_series.send(
            self.data[self.indices] if self.data else None)

    @classmethod
    def migrate_context(cls, context, version):
        if version < 2:
            values = context.values
            context.values["agg_attr"] = values["agg_attr"][0][0]
            _, type = values["agg_attr"]
            ind, pos = values["agg_func"]
            if type == 101: # discrete variable is always Mode in old settings
                context.values["agg_func"] = ('Mode', pos)
            else:
                context.values["agg_func"] = (list(AGG_OPTIONS)[ind], pos)


if __name__ == "__main__":
    WidgetPreview(OWSpiralogram).run(Table.from_file('airpassengers'))
