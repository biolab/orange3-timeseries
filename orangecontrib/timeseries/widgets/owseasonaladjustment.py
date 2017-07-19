import numpy as np

from AnyQt.QtWidgets import QListView
from AnyQt.QtCore import Qt

from Orange.data import Table, Domain
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.itemmodels import VariableListModel

from orangecontrib.timeseries import Timeseries, seasonal_decompose


class Output:
    TIMESERIES = 'Time series'


class OWSeasonalAdjustment(widget.OWWidget):
    name = 'Seasonal Adjustment'
    description = 'Remove the seasonal component of a time series that ' \
                  'exhibits a seasonal pattern.'
    icon = 'icons/SeasonalAdjustment.svg'
    priority = 5500

    inputs = [("Time series", Table, 'set_data')]
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
        self.data = data = None if data is None else Timeseries.from_data_table(data)
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

        selected_subset = Timeseries(Domain(self.selected, source=data.domain), data)  # FIXME: might not pass selected interpolation method

        with self.progressBar(len(self.selected)) as progress:
            adjusted_data = seasonal_decompose(
                selected_subset,
                self.DECOMPOSITION_MODELS[self.decomposition],
                self.n_periods,
                callback=lambda *_: progress.advance())

        ts = Timeseries(Timeseries.concatenate((data, adjusted_data)))
        ts.time_variable = data.time_variable
        self.send(Output.TIMESERIES, ts)


if __name__ == "__main__":
    from AnyQt.QtWidgets import QApplication

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
