from collections import OrderedDict

import numpy as np

from AnyQt.QtCore import QSize

from Orange.data import Table
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.itemmodels import PyTableModel
from Orange.widgets.widget import Input

from orangecontrib.timeseries import Timeseries, model_evaluation
from orangecontrib.timeseries.models import _BaseModel
from orangewidget.utils.widgetpreview import WidgetPreview


class Output:
    TIMESERIES = 'Time series'


class OWModelEvaluation(widget.OWWidget):
    name = 'Model Evaluation'
    description = '''Evaluate different time series' models by comparing the
                  errors they make in terms of:
                  root mean squared error (RMSE),
                  median absolute error (MAE),
                  mean absolute percent error (MAPE),
                  prediction of change in direction (POCID),
                  coefficient of determination (R²),
                  Akaike information criterion (AIC), and
                  Bayesian information criterion (BIC).
                  '''
    icon = 'icons/ModelEvaluation.svg'
    priority = 300

    class Inputs:
        time_series = Input("Time series", Table)
        time_series_model = Input("Time series model", _BaseModel, multiple=True)

    n_folds = settings.Setting(20)
    forecast_steps = settings.Setting(3)
    autocommit = settings.Setting(False)

    class Error(widget.OWWidget.Error):
        unexpected_error = widget.Msg('Unexpected error: {}')

    class Warning(widget.OWWidget.Warning):
        model_failed = widget.Msg('One or more models failed.')

    def __init__(self):
        self.data = None
        self._models = OrderedDict()
        box = gui.vBox(self.controlArea, 'Evaluation Parameters')
        gui.spin(box, self, 'n_folds', 1, 100,
                 label='Number of folds:',
                 callback=self.commit.deferred)
        gui.spin(box, self, 'forecast_steps', 1, 100,
                 label='Forecast steps:',
                 callback=self.commit.deferred)
        gui.auto_commit(self.buttonsArea, self, 'autocommit', '&Apply')
        gui.rubber(self.controlArea)

        self.model = model = PyTableModel(parent=self)
        view = gui.TableView(self)
        view.setModel(model)
        view.horizontalHeader().setStretchLastSection(False)
        view.verticalHeader().setVisible(True)
        self.mainArea.layout().addWidget(view)

    def sizeHint(self):
        return QSize(650, 175)

    @Inputs.time_series
    def set_data(self, data):
        self.data = None if data is None else Timeseries.from_data_table(data)

    @Inputs.time_series_model
    def set_model(self, model, id):
        if model is None:
            self._models.pop(id, None)
        else:
            self._models[id] = model.copy()

    def handleNewSignals(self):
        self.commit.now()

    @gui.deferred
    def commit(self):
        self.Error.unexpected_error.clear()
        self.Warning.model_failed.clear()
        self.model.clear()
        data = self.data
        if not data or not self._models:
            return
        try:
            with self.progressBar(len(self._models) * (self.n_folds + 1) + 1) as progress:
                res = model_evaluation(data, list(self._models.values()),
                                       self.n_folds, self.forecast_steps,
                                       callback=progress.advance)
        except ValueError as e:
            self.Error.unexpected_error(e.args[0])
            return
        res = np.array(res, dtype=object)
        self.Warning.model_failed(shown="err" in res)
        self.model.setHorizontalHeaderLabels(res[0, 1:].tolist())
        self.model.setVerticalHeaderLabels(res[1:, 0].tolist())
        self.model.wrap(res[1:, 1:].tolist())


if __name__ == "__main__":
    class BadModel(_BaseModel):
        def _predict(self):
            return 1 / 0

    from orangecontrib.timeseries import ARIMA, VAR
    data = Timeseries.from_file('airpassengers')
    learners = [ARIMA((1, 1, 1)), ARIMA((2, 1, 0)), VAR(1), VAR(5), BadModel()]
    WidgetPreview(OWModelEvaluation).run(
        set_data=data,
        set_model=[(model, i) for i, model in enumerate(learners)]
    )
