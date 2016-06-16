from operator import sub, truediv
import numpy as np

from PyQt4.QtGui import QListView
from PyQt4.QtCore import Qt
from statsmodels.tsa.seasonal import seasonal_decompose

from Orange.data import Domain, ContinuousVariable
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.itemmodels import VariableListModel

from orangecontrib.timeseries import Timeseries
from orangecontrib.timeseries.widgets.utils import available_name


class Output:
    TIMESERIES = 'Time series'


class OWSeasonalAdjustment(widget.OWWidget):
    name = 'Seasonal Adjustment'
    description = 'Remove the seasonal component of a time series that ' \
                  'exhibits a seasonal pattern.'
    icon = 'icons/SeasonalAdjustment.svg'
    priority = 5500

    inputs = [("Time series", Timeseries, 'set_data')]
    outputs = [("Time series", Timeseries)]

    want_main_area = False
    resizing_enabled = False

    n_periods = settings.Setting(12)
    decomposition = settings.Setting(0)
    selected = settings.Setting([])
    autocommit = settings.Setting(False)

    UserAdviceMessages = [
        widget.Message('An additive model is appropriate if the magnitude of '
                       'seasonal fluctuations doesn\'t vary with level. '
                       'Otherwise, a multiplicative model is appropriate. '
                       'Taking logarithms of series turns a multiplicative '
                       'relationship into an additive one. '
                       'Multiplicative decomposition is more prevalent '
                       'with economic time series.',
                       'decomposition-model'),
        widget.Message('Season period is the length of the whole season cycle.'
                       'E.g., if you have hourly electricity use data, and '
                       'the series apparently makes a cycle every day, the '
                       'appropriate period is 24. The value should likely '
                       'correspond to one of the most significant periods '
                       'in periodogram.',
                       'season-period'),
    ]

    DECOMPOSITION_MODELS = ('additive', 'multiplicative')

    def __init__(self):
        self.data = None
        box = gui.vBox(self.controlArea, 'Seasonal Adjustment')
        gui.spin(box, self, 'n_periods', 2, 1000,
                 label='Season period:',
                 callback=self.on_changed,
                 tooltip='The expected length of full cycle. E.g., if you have '
                         'monthly data and the apparent season repeats every '
                         'year, you put in 12.')
        gui.radioButtons(box, self, 'decomposition', self.DECOMPOSITION_MODELS,
                         label='Decomposition model:',
                         orientation=Qt.Horizontal,
                         callback=self.on_changed)
        self.view = view = QListView(self,
                                     selectionMode=QListView.ExtendedSelection)
        self.model = model = VariableListModel(parent=self)
        view.setModel(model)
        view.selectionModel().selectionChanged.connect(self.on_changed)
        box.layout().addWidget(view)
        gui.auto_commit(box, self, 'autocommit', '&Apply')

    def set_data(self, data):
        self.data = data
        if data is not None:
            self.model.wrap([var for var in data.domain
                             if var.is_continuous and var is not data.time_variable])
        self.on_changed()

    def on_changed(self):
        self.selected = [self.model[i.row()].name
                         for i in self.view.selectionModel().selectedIndexes()]
        self.commit()

    def commit(self):
        data = self.data
        if not data or not self.selected:
            self.send(Output.TIMESERIES, data)
            return

        def _interp_trend(trend):
            first = next(i for i, val in enumerate(trend) if val == val)
            last = trend.size - 1 - next(i for i, val in enumerate(trend[::-1]) if val == val)
            d = 3
            first_last = min(first + d, last)
            last_first = max(first, last - d)

            k, n = np.linalg.lstsq(
                np.column_stack((np.arange(first, first_last), np.ones(d))),
                trend[first:first_last])[0]
            trend[:first] = np.arange(0, first) * k + n

            k, n = np.linalg.lstsq(
                np.column_stack((np.arange(last_first, last), np.ones(d))),
                trend[last_first:last])[0]
            trend[last + 1:] = np.arange(last + 1, trend.size) * k + n
            return trend

        attrs = []
        X = []
        decomposition = self.DECOMPOSITION_MODELS[self.decomposition]
        recomposition = sub if decomposition == 'additive' else truediv
        interp_data = data.interp()
        with self.progressBar(len(self.selected)) as progress:
            for var in self.selected:
                decomposed = seasonal_decompose(np.ravel(interp_data[:, var]),
                                                model=decomposition,
                                                freq=self.n_periods)
                adjusted = recomposition(decomposed.observed,
                                           decomposed.seasonal)

                season = decomposed.seasonal
                trend = _interp_trend(decomposed.trend)
                resid = recomposition(adjusted, trend)

                # Re-apply nans
                isnan = np.isnan(data[:, var]).ravel()
                adjusted[isnan] = np.nan
                trend[isnan] = np.nan
                resid[isnan] = np.nan

                attrs.extend(
                    ContinuousVariable(
                        available_name(data.domain,
                                       var + ' ({})'.format(transform)))
                    for transform in ('season. adj.', 'seasonal', 'trend', 'residual')
                )
                X.extend((adjusted, season, trend, resid))
                progress.advance()

        ts = Timeseries(Domain(data.domain.attributes + tuple(attrs),
                               data.domain.class_vars,
                               data.domain.metas),
                        np.column_stack((data.X, np.column_stack(X))),
                        data.Y, data.metas)
        ts.time_variable = data.time_variable
        self.send(Output.TIMESERIES, ts)


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication

    a = QApplication([])
    ow = OWSeasonalAdjustment()

    # data = Timeseries('yahoo_MSFT')
    data = Timeseries('airpassengers')
    if not data.domain.class_var and 'Adj Close' in data.domain:
        # Make Adjusted Close a class variable
        attrs = [var.name for var in data.domain.attributes]
        attrs.remove('Adj Close')
        data = Timeseries(Domain(attrs, [data.domain['Adj Close']], None, source=data.domain), data)

    ow.set_data(data)

    ow.show()
    a.exec()
