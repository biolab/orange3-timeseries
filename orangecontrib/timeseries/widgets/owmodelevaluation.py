from collections import OrderedDict

import numpy as np

from PyQt4.QtCore import QSize

from Orange.data import Table
from Orange.widgets import widget, gui, settings
from Orange.widgets.utils.itemmodels import PyTableModel

from orangecontrib.timeseries import Timeseries, model_evaluation
from orangecontrib.timeseries.models import _BaseModel


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

    inputs = [("Time series", Table, 'set_data'),
              ("Time series model", _BaseModel, 'set_model', widget.Multiple)]

    n_folds = settings.Setting(20)
    forecast_steps = settings.Setting(3)
    autocommit = settings.Setting(False)

    class Error(widget.OWWidget.Error):
        unexpected_error = widget.Msg('Unexpected error: {}')

    def __init__(self):
        self.data = None
        self._models = OrderedDict()
        box = gui.vBox(self.controlArea, 'Evaluation Parameters')
        gui.spin(box, self, 'n_folds', 1, 100,
                 label='Number of folds:',
                 callback=self.on_changed)
        gui.spin(box, self, 'forecast_steps', 1, 100,
                 label='Forecast steps:',
                 callback=self.on_changed)
        gui.auto_commit(box, self, 'autocommit', '&Apply')
        gui.rubber(self.controlArea)

        self.model = model = PyTableModel(parent=self)
        view = gui.TableView(self)
        view.setModel(model)
        view.horizontalHeader().setStretchLastSection(False)
        view.verticalHeader().setVisible(True)
        self.mainArea.layout().addWidget(view)

    def sizeHint(self):
        return QSize(650, 175)

    def set_data(self, data):
        self.data = data = None if data is None else Timeseries.from_data_table(data)
        self.on_changed()

    def set_model(self, model, id):
        if model is None:
            self._models.pop(id, None)
        else:
            self._models[id] = model.copy()
        self.on_changed()

    def on_changed(self):
        self.commit()

    def commit(self):
        self.Error.unexpected_error.clear()
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
        self.model.setHorizontalHeaderLabels(res[0, 1:].tolist())
        self.model.setVerticalHeaderLabels(res[1:, 0].tolist())
        self.model.wrap(res[1:, 1:].tolist())


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    from Orange.data import Domain
    from orangecontrib.timeseries import ARIMA, VAR

    a = QApplication([])
    ow = OWModelEvaluation()

    data = Timeseries('yahoo_MSFT')
    # Make Adjusted Close a class variable
    attrs = [var.name for var in data.domain.attributes]
    if 'Adj Close' in attrs:
        attrs.remove('Adj Close')
        data = Timeseries(Domain(attrs, [data.domain['Adj Close']], None, source=data.domain), data)

    ow.set_data(data)
    ow.set_model(ARIMA((1, 1, 1)), 1)
    ow.set_model(ARIMA((2, 1, 0)), 2)
    # ow.set_model(ARIMA((0, 1, 1)), 3)
    # ow.set_model(ARIMA((4, 1, 0)), 4)
    ow.set_model(VAR(1), 11)
    ow.set_model(VAR(5), 12)
    # ow.set_model(VAR(6), 14)

    ow.show()
    a.exec()
