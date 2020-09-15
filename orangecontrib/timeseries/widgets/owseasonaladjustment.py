from AnyQt.QtWidgets import QListView
from AnyQt.QtCore import Qt

from Orange.data import Table, Domain
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.itemmodels import VariableListModel
from Orange.widgets.widget import Input, Output, Msg
from numpy import hstack

from orangecontrib.timeseries import Timeseries, seasonal_decompose


MAX_PERIODS = 1000


class OWSeasonalAdjustment(widget.OWWidget):
    name = 'Seasonal Adjustment'
    description = 'Remove the seasonal component of a time series that ' \
                  'exhibits a seasonal pattern.'
    icon = 'icons/SeasonalAdjustment.svg'
    priority = 5500

    class Inputs:
        time_series = Input("Time series", Table)

    class Outputs:
        time_series = Output("Time series", Timeseries)

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

    class Error(widget.OWWidget.Error):
        seasonal_decompose_fail = Msg("{}")
        not_enough_instances = Msg("Time series has to have at least 3 instances.")

    def __init__(self):
        self.data = None
        box = gui.vBox(self.controlArea, 'Seasonal Adjustment')
        gui.spin(box, self, 'n_periods', 2, MAX_PERIODS,
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

    @Inputs.time_series
    def set_data(self, data):
        self.Error.not_enough_instances.clear()
        self.data = None
        self.model.clear()
        data = None if data is None else Timeseries.from_data_table(data)
        if data is None:
            pass
        elif len(data) > 2:
            self.data = data
            self.model.wrap([var for var in data.domain.variables
                             if var.is_continuous and var is not data.time_variable])
            self.controls.n_periods.setMaximum(min(MAX_PERIODS, len(data) - 1))
        else:
            self.Error.not_enough_instances()
        self.on_changed()

    def on_changed(self):
        self.selected = [self.model[i.row()].name
                         for i in self.view.selectionModel().selectedIndexes()]
        self.commit()

    def commit(self):
        self.Error.seasonal_decompose_fail.clear()
        data = self.data
        if not data or not self.selected:
            self.Outputs.time_series.send(data)
            return

        selected_subset = Timeseries.from_table(Domain(self.selected,
                                                source=data.domain), data)
        # FIXME: might not pass selected interpolation method

        with self.progressBar(len(self.selected)) as progress:
            try:
                adjusted_data = seasonal_decompose(
                    selected_subset,
                    self.DECOMPOSITION_MODELS[self.decomposition],
                    self.n_periods,
                    callback=lambda *_: progress.advance())
            except ValueError as ex:
                self.Error.seasonal_decompose_fail(str(ex))
                adjusted_data = None

        if adjusted_data is not None:
            new_domain = Domain(data.domain.attributes +
                                adjusted_data.domain.attributes,
                                data.domain.class_vars,
                                data.domain.metas)
            ts = Timeseries.from_numpy(new_domain, X=hstack((data.X,
                                                       adjusted_data.X)),
                                                   Y=data.Y,
                                                   metas=data.metas)
            ts.time_variable = data.time_variable
        else:
            ts = None
        self.Outputs.time_series.send(ts)


if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication

    a = QApplication([])
    ow = OWSeasonalAdjustment()

    data = Timeseries.from_file('airpassengers')
    if not data.domain.class_var and 'Adj Close' in data.domain:
        # Make Adjusted Close a class variable
        attrs = [var.name for var in data.domain.attributes]
        attrs.remove('Adj Close')
        data = Timeseries.from_table(Domain(attrs, [data.domain['Adj Close']], None,
                                            source=data.domain),
                                     data)

    ow.set_data(data)

    ow.show()
    a.exec()
